import os
import re
import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from prompt import SYSTEM_PROMPT
from tools import TOOLS

load_dotenv()

# ---- Safety / budget configuration -----------------------------------
MAX_STEPS = 10               # hard cap on total reasoning/tool steps
MAX_EMPTY_RESPONSES = 3       # abort after this many consecutive empty replies
MAX_SAME_TOOL_CALLS = 3       # abort if one tool is called this many times in a row
MAX_INVALID_TOOL_NAMES = 3    # abort after this many unrecognized "TOOL:" lines
MAX_RETRIES_ON_API_ERROR = 3
RETRY_BACKOFF_SECONDS = 2
MAX_HISTORY_MESSAGES = 30     # trim oldest turns if the conversation grows too long

TOOL_LINE_RE = re.compile(r"^TOOL:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*$")

llm = ChatOpenAI(
    model="openrouter/free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "http://localhost",
        "X-Title": "Autonomous Agents",
    },
    temperature=0,
)

case_description = """
Passenger flight delayed 6 hours because of bad weather.

Passenger has a connecting flight.

Passenger is traveling with family.

The passenger wants to continue the journey as soon as possible.

No information about available flights.
"""

messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=case_description),
]


def trim_history(msgs):
    """Keep the system message plus the most recent turns, so the context
    doesn't grow without bound over a long run."""
    if len(msgs) <= MAX_HISTORY_MESSAGES:
        return msgs
    system = msgs[0]
    recent = msgs[-(MAX_HISTORY_MESSAGES - 1):]
    return [system] + recent


def safe_invoke(msgs):
    """Call the LLM with retries/backoff instead of crashing on the first
    network or rate-limit error."""
    last_error = None
    for attempt in range(1, MAX_RETRIES_ON_API_ERROR + 1):
        try:
            return llm.invoke(msgs)
        except Exception as exc:  # network errors, 429s, etc.
            last_error = exc
            print(f"\n[warning] LLM call failed (attempt {attempt}/{MAX_RETRIES_ON_API_ERROR}): {exc}")
            if attempt < MAX_RETRIES_ON_API_ERROR:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"LLM call failed after {MAX_RETRIES_ON_API_ERROR} attempts") from last_error


def clean_answer(raw_text):
    """Strip stray safety-classifier / tag leakage lines from the raw model
    output before we try to interpret it."""
    filtered = []
    for line in raw_text.splitlines():
        if "User Safety" in line:
            continue
        if "Response Safety" in line:
            continue
        if "<tool_call>" in line:
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def run():
    step = 1
    empty_response_count = 0
    invalid_tool_count = 0
    last_tool_name = None
    same_tool_streak = 0

    while step <= MAX_STEPS:

        messages[:] = trim_history(messages)

        try:
            response = safe_invoke(messages)
        except RuntimeError as exc:
            print(f"\n=== Aborting: {exc} ===")
            return

        answer = clean_answer(response.content.strip())

        # --- guard: empty response -------------------------------------
        if not answer:
            empty_response_count += 1
            print(f"\n[warning] Empty response from model ({empty_response_count}/{MAX_EMPTY_RESPONSES})")
            if empty_response_count >= MAX_EMPTY_RESPONSES:
                print("\n=== Aborting: too many empty responses ===")
                return
            # Nudge the model instead of silently looping on identical state
            messages.append(
                HumanMessage(content="Your last response was empty. Reply with either a TOOL: line or a FINAL: recommendation.")
            )
            continue

        empty_response_count = 0

        # --- FINAL --------------------------------------------------------
        if answer.upper().startswith("FINAL"):
            print("\n=== Final ===")
            print(answer)
            return

        # --- TOOL -----------------------------------------------------
        tool_match = TOOL_LINE_RE.match(answer.strip())

        if tool_match:
            tool_name = tool_match.group(1)

            if tool_name in TOOLS:
                # repetition guard
                if tool_name == last_tool_name:
                    same_tool_streak += 1
                else:
                    same_tool_streak = 1
                last_tool_name = tool_name

                if same_tool_streak > MAX_SAME_TOOL_CALLS:
                    print(f"\n=== Aborting: '{tool_name}' called {same_tool_streak} times in a row ===")
                    return

                print(f"\n=== Step {step} ===")
                print(answer)

                observation = TOOLS[tool_name]()

                print("\nObservation:")
                print(observation)

                messages.append(AIMessage(content=answer))
                messages.append(HumanMessage(content=f"Observation: {observation}"))
                step += 1

            else:
                invalid_tool_count += 1
                print(f"\n[warning] Unknown tool requested: '{tool_name}' ({invalid_tool_count}/{MAX_INVALID_TOOL_NAMES})")
                if invalid_tool_count >= MAX_INVALID_TOOL_NAMES:
                    print("\n=== Aborting: too many invalid tool names ===")
                    return
                messages.append(AIMessage(content=answer))
                messages.append(
                    HumanMessage(
                        content=(
                            f"'{tool_name}' is not a valid tool. Valid tools are: "
                            f"{', '.join(TOOLS.keys())}. Reply with a single TOOL: line."
                        )
                    )
                )

        else:
            # Free-form reasoning step (not a strict TOOL/FINAL line)
            print(f"\n=== Reasoning {step} ===")
            print(answer)
            messages.append(AIMessage(content=answer))
            step += 1

    # --- step budget exhausted: force a best-effort final answer ---------
    print(f"\n=== Step limit reached ({MAX_STEPS}) — forcing a final recommendation ===")
    messages.append(
        HumanMessage(
            content="You have reached your step limit. Reply now with FINAL: and your best recommendation based on what you know so far."
        )
    )
    try:
        response = safe_invoke(messages)
        answer = clean_answer(response.content.strip())
    except RuntimeError as exc:
        print(f"\n=== Could not obtain a final answer: {exc} ===")
        return

    print("\n=== Final (forced) ===")
    print(answer if answer else "(model returned no content)")


if __name__ == "__main__":
    run()
