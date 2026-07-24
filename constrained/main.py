import json
import os
import time

from dotenv import load_dotenv
from pydantic import ValidationError
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from prompt import SYSTEM_PROMPT
from tools import TOOLS
from schema import AgentStep, ALLOWED_TOOLS

load_dotenv()

# ---- Safety / budget configuration -----------------------------------
# These constants are intentionally kept together, at the top of the file,
# so the constraints defining this architecture are easy to find.
MAX_STEPS = 10                 # hard cap on total reasoning/tool steps
MAX_VALIDATION_RETRIES = 3     # bounded retries when the model's JSON fails schema validation
MAX_SAME_TOOL_CALLS = 3        # abort if one tool is called this many times in a row
MAX_RETRIES_ON_API_ERROR = 3
RETRY_BACKOFF_SECONDS = 2
MAX_HISTORY_MESSAGES = 30      # trim oldest turns if the conversation grows too long

TOOL_ALLOW_LIST = ALLOWED_TOOLS  # re-exported here for visibility, same source as schema.py

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


def strip_code_fences(raw_text):
    """Models sometimes wrap JSON in ```json ... ``` even when told not to.
    Strip that before parsing, without silently accepting other prose."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_and_validate(raw_text):
    """Parse the model's raw output as JSON and validate it against the
    AgentStep schema. Returns (step, error_message). Exactly one is None."""
    text = strip_code_fences(raw_text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"Your response was not valid JSON ({exc}). Respond with a single JSON object only."

    try:
        step = AgentStep(**payload)
    except ValidationError as exc:
        # Compact, model-readable summary of what was wrong.
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        return None, f"Your JSON did not match the required schema: {problems}."

    return step, None


def run():
    step_count = 1
    validation_failures = 0
    last_tool_name = None
    same_tool_streak = 0

    while step_count <= MAX_STEPS:

        messages[:] = trim_history(messages)

        try:
            response = safe_invoke(messages)
        except RuntimeError as exc:
            print(f"\n=== Aborting: {exc} ===")
            return

        raw_answer = response.content.strip()
        step, error = parse_and_validate(raw_answer)

        # --- guard: schema validation failure ---------------------------
        if error:
            validation_failures += 1
            print(f"\n[warning] Schema validation failed ({validation_failures}/{MAX_VALIDATION_RETRIES}): {error}")
            if validation_failures >= MAX_VALIDATION_RETRIES:
                print("\n=== Escalating: model could not produce a schema-valid step ===")
                print(f"Reason: repeated invalid output after {MAX_VALIDATION_RETRIES} attempts.")
                return
            messages.append(AIMessage(content=raw_answer))
            messages.append(HumanMessage(content=f"Invalid step. {error} Try again with a single valid JSON object."))
            continue

        validation_failures = 0

        # --- FINAL --------------------------------------------------------
        if step.action == "final":
            print("\n=== Final ===")
            print(step.final_answer)
            return

        # --- ESCALATE -------------------------------------------------
        if step.action == "escalate":
            print("\n=== Escalated to a human agent ===")
            print(f"Reason: {step.escalate_reason}")
            return

        # --- TOOL_CALL --------------------------------------------------
        tool_name = step.tool_name  # already validated against the allow-list by the schema

        # repetition guard
        if tool_name == last_tool_name:
            same_tool_streak += 1
        else:
            same_tool_streak = 1
        last_tool_name = tool_name

        if same_tool_streak > MAX_SAME_TOOL_CALLS:
            print(f"\n=== Escalating: '{tool_name}' called {same_tool_streak} times in a row ===")
            return

        print(f"\n=== Step {step_count} ===")
        print(f"tool_call: {tool_name}")

        observation = TOOLS[tool_name]()

        print("\nObservation:")
        print(observation)

        messages.append(AIMessage(content=raw_answer))
        messages.append(HumanMessage(content=f"Observation: {observation}"))
        step_count += 1

    # --- step budget exhausted: force a best-effort final or escalate ----
    print(f"\n=== Step limit reached ({MAX_STEPS}) — forcing a final decision ===")
    messages.append(
        HumanMessage(
            content=(
                "You have reached your step limit. Respond now with a single JSON object: "
                'either {"action": "final", "final_answer": "..."} with your best recommendation, '
                'or {"action": "escalate", "escalate_reason": "..."} if you cannot responsibly finish.'
            )
        )
    )
    try:
        response = safe_invoke(messages)
        step, error = parse_and_validate(response.content.strip())
    except RuntimeError as exc:
        print(f"\n=== Could not obtain a final answer: {exc} ===")
        return

    if error or step.action == "tool_call":
        print("\n=== Escalating: could not obtain a valid final/escalate step within budget ===")
        return

    if step.action == "final":
        print("\n=== Final (forced) ===")
        print(step.final_answer)
    else:
        print("\n=== Escalated to a human agent (forced) ===")
        print(f"Reason: {step.escalate_reason}")


if __name__ == "__main__":
    run()
