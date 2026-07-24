from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

import json
import os

from prompt import SYSTEM_PROMPT
from tools import TOOLS

def format_observation(observation):

    if isinstance(observation, list):

        if len(observation) == 0:
            return "No results found."

        lines = []

        for item in observation:

            if isinstance(item, dict):

                lines.append(
                    f"Flight: {item['flight_number']} | "
                    f"Departure: {item['departure']} | "
                    f"Status: {item['status']}"
                )

            else:

                lines.append(str(item))

        return "\n".join(lines)

    return str(observation)


load_dotenv()

with open("data/airline_data.json", "r") as f:
    DATA = json.load(f)

case = DATA["cases"]["case_1"]

llm = ChatOpenAI(
    model="openrouter/free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "http://localhost",
        "X-Title": "Autonomous Agents",
    },
    temperature=0.7,
)

case_description = f"""
Passenger flight delayed {case['delay_hours']} hours because of {case['delay_reason']}.

Passenger {'has a connecting flight' if case['has_connecting_flight'] else 'has no connecting flight'}.

Passenger is {'traveling with family' if case['traveling_with_family'] else 'traveling alone'}.

Passenger {'wants to continue the journey as soon as possible' if case['wants_earliest_flight'] else 'does not want the earliest available flight'}.

{'No information about available flights.' if not case['available_flight_information'] else 'Flight information is available.'}
"""
messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=case_description),
]

step = 1

while True:

    response = llm.invoke(messages)

    answer = response.content.strip()

    filtered = []

    for line in answer.splitlines():

        if "User Safety" in line:
            continue

        if "Response Safety" in line:
            continue

        if "<tool_call>" in line:
            continue

        filtered.append(line)

    answer = "\n".join(filtered).strip()

    if not answer:
        continue

    if answer.upper().startswith("FINAL"):

        print("\n========== FINAL ANSWER ==========\n")
        print(answer)
        break

    elif answer.startswith("TOOL:"):

        tool_name = answer.split(":", 1)[1].strip()

        print(f"\n========== STEP {step} ==========")
        print(f"Action : {tool_name}")

        if tool_name not in TOOLS:

            observation = (
                f"ERROR: Tool '{tool_name}' does not exist."
            )

        else:

            if tool_name == "check_available_flights":

                observation = TOOLS[tool_name](case_description)

            else:

                observation = TOOLS[tool_name]()

        print("\nObservation:")
        print(format_observation(observation))
        
        messages.append(AIMessage(content=answer))

        messages.append(
            HumanMessage(
                content=f"Observation: {observation}"
            )
        )

        step += 1

    else:

        print(f"\n========== MODEL RESPONSE ==========\n")
        print(answer)

        messages.append(AIMessage(content=answer))