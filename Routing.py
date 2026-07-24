"""
Deterministic Routing Agent — Flight Disruption
================================================
ONE LLM call → classifies the case into a fixed category.
Everything after that is ordinary Python code — no more model calls.

Categories:
  MINOR_DELAY        → delay < 2 hours
  MEDIUM_DELAY       → delay 2–6 hours
  MAJOR_DELAY        → delay > 6 hours
  MISSED_CONNECTION  → passenger will miss a connecting flight
  CANCELLATION       → flight fully cancelled
  ESCALATE           → complex / unclear — send to human agent
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from tools import (
    check_available_flights,
    issue_meal_voucher,
    notify_hotel,
    offer_travel_credit,
    escalate_to_human,
)

load_dotenv()

# ── LLM setup (same provider as main.py from the team) ────
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

# ── The ONLY prompt / LLM call in this entire agent ────────
CLASSIFIER_PROMPT = """
You are a flight disruption classifier for Blue Horizons Airlines.

Read the passenger case below and respond with EXACTLY ONE of these labels — nothing else, no explanation:

MINOR_DELAY
MEDIUM_DELAY
MAJOR_DELAY
MISSED_CONNECTION
CANCELLATION
ESCALATE

Rules:
- MINOR_DELAY: delay is less than 2 hours and no connection at risk
- MEDIUM_DELAY: delay is 2 to 6 hours and no connection at risk
- MAJOR_DELAY: delay is more than 6 hours and no connection at risk
- MISSED_CONNECTION: passenger will miss a connecting flight regardless of delay length
- CANCELLATION: the flight is fully cancelled
- ESCALATE: the situation is complex, ambiguous, or doesn't fit any category above

Respond with the label only. One word or two words. Nothing else.
"""


ALLOWED_CATEGORIES = {
    "MINOR_DELAY",
    "MEDIUM_DELAY",
    "MAJOR_DELAY",
    "MISSED_CONNECTION",
    "CANCELLATION",
    "ESCALATE",
}


def classify_case(case_description: str) -> str:
    """Single LLM call — returns one category label."""
    messages = [
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=case_description),
    ]
    response = llm.invoke(messages)
    label = response.content.strip().upper()

    # Safety: if model returns something unexpected, escalate
    if label not in ALLOWED_CATEGORIES:
        print(f"  [Warning] Unexpected label '{label}' → defaulting to ESCALATE")
        label = "ESCALATE"

    return label


# ── Fixed workflow functions (zero LLM calls inside) ───────

def handle_minor_delay():
    print("  → Sending apology message to passenger.")
    return "Apology sent. No compensation for delays under 2 hours."


def handle_medium_delay(membership: str = "standard"):
    actions = []
    voucher = issue_meal_voucher()
    actions.append(voucher)
    result = "Meal voucher issued."

    if membership in ("gold", "silver"):
        credit = offer_travel_credit()
        actions.append(credit)
        result += f" {membership.capitalize()} member bonus: travel credit added."

    for a in actions:
        print(f"  → {a}")
    return result


def handle_major_delay():
    actions = []
    hotel = notify_hotel()
    actions.append(hotel)
    flights = check_available_flights()
    actions.append(f"Rebooking options: {flights}")

    for a in actions:
        print(f"  → {a}")
    return "Hotel booked. Passenger offered rebooking on next available flight."


def handle_missed_connection():
    flights = check_available_flights()
    print(f"  → Rebooking options: {flights}")
    return f"Connection missed. Passenger rebooked. Options: {flights}"


def handle_cancellation(passenger_request: str = "none"):
    actions = []
    credit = offer_travel_credit()
    actions.append(credit)
    flights = check_available_flights()
    actions.append(f"Rebooking options: {flights}")

    if passenger_request == "refund":
        actions.append("Passenger requested full refund — escalating refund request.")

    for a in actions:
        print(f"  → {a}")
    return "Cancellation handled: travel credit issued + rebooking offered."


def handle_escalate():
    result = escalate_to_human()
    print(f"  → {result}")
    return result


# ── Dispatcher: routes label → workflow ────────────────────

WORKFLOWS = {
    "MINOR_DELAY":       lambda case: handle_minor_delay(),
    "MEDIUM_DELAY":      lambda case: handle_medium_delay(case.get("membership", "standard")),
    "MAJOR_DELAY":       lambda case: handle_major_delay(),
    "MISSED_CONNECTION": lambda case: handle_missed_connection(),
    "CANCELLATION":      lambda case: handle_cancellation(case.get("passenger_request", "none")),
    "ESCALATE":          lambda case: handle_escalate(),
}


def routing_agent(case: dict, case_description: str):
    print("=" * 55)
    print("ROUTING AGENT — Flight Disruption Handler")
    print("=" * 55)
    print("Case description sent to classifier:")
    print(f"  {case_description.strip()}")
    print("-" * 55)

    # ── Step 1: ONE LLM call to classify ──────────────────
    print("\n[Step 1] Classifying case (1 LLM call)...")
    label = classify_case(case_description)
    print(f"  → Category: {label}")

    # ── Step 2: Deterministic workflow — no more LLM ──────
    print("\n[Step 2] Running fixed workflow (zero LLM calls)...")
    workflow = WORKFLOWS.get(label, lambda _: handle_escalate())
    result = workflow(case)

    print(f"\nFinal Recommendation:\n  {result}")
    print("=" * 55)
    return {"category": label, "result": result}


# ── Test cases ─────────────────────────────────────────────

if __name__ == "__main__":

    test_cases = [
        (
            {
                "delay_hours": 3,
                "cancelled": False,
                "has_connection": False,
                "membership": "silver",
                "passenger_request": "none",
            },
            "Passenger flight delayed 3 hours due to a technical fault. Silver member. No connecting flight."
        ),
        (
            {
                "delay_hours": 1,
                "cancelled": False,
                "has_connection": True,
                "membership": "standard",
                "passenger_request": "rebook",
            },
            "Flight delayed 1 hour because of bad weather. Passenger has a connecting flight that departs in 90 minutes."
        ),
        (
            {
                "delay_hours": 0,
                "cancelled": True,
                "has_connection": False,
                "membership": "gold",
                "passenger_request": "refund",
            },
            "Flight MS101 has been fully cancelled due to crew shortage. Gold member passenger is requesting a refund."
        ),
        (
            {
                "delay_hours": 9,
                "cancelled": False,
                "has_connection": False,
                "membership": "standard",
                "passenger_request": "hotel",
            },
            "Passenger flight delayed 9 hours due to aircraft mechanical issue. Passenger is traveling with family and needs accommodation."
        ),
    ]

    for i, (case, description) in enumerate(test_cases, 1):
        print(f"\n{'#'*55}")
        print(f"  TEST CASE {i}")
        print(f"{'#'*55}")
        routing_agent(case, description)
