"""
Reactive (Rule-Based) Agent — Flight Disruption
================================================
No LLM. No AI. Pure if/then conditions.
The agent observes the case data and applies fixed rules.
"""

from tools import check_available_flights, issue_meal_voucher, notify_hotel, offer_travel_credit


def reactive_agent(case: dict) -> dict:
    """
    Takes a case dictionary and returns a decision dictionary.
    Applies hard-coded rules in order — no reasoning, no model.
    """
    delay_hours = case.get("delay_hours", 0)
    cancelled = case.get("cancelled", False)
    has_connection = case.get("has_connection", False)
    membership = case.get("membership", "standard")   # standard | silver | gold
    passenger_request = case.get("passenger_request", "none")  # refund | hotel | rebook | none

    actions_taken = []
    recommendation = ""

    print("=" * 50)
    print("REACTIVE AGENT — Flight Disruption Handler")
    print("=" * 50)
    print(f"Delay: {delay_hours} hours | Cancelled: {cancelled}")
    print(f"Connection: {has_connection} | Membership: {membership}")
    print(f"Passenger request: {passenger_request}")
    print("-" * 50)

    # ── Rule 1: Full cancellation ──────────────────────────
    if cancelled:
        result = offer_travel_credit()
        actions_taken.append(result)
        recommendation = "Flight cancelled → full travel credit issued. Rebook on next available flight."
        flights = check_available_flights()
        actions_taken.append(f"Available flights: {flights}")

    # ── Rule 2: Passenger will miss a connecting flight ────
    elif has_connection and delay_hours >= 1:
        flights = check_available_flights()
        actions_taken.append(f"Available flights: {flights}")
        recommendation = "Connection at risk → rebooked on next available flight."

    # ── Rule 3: Long delay (> 6 hours) ────────────────────
    elif delay_hours > 6:
        hotel = notify_hotel()
        actions_taken.append(hotel)
        flights = check_available_flights()
        actions_taken.append(f"Available flights: {flights}")
        recommendation = "Delay > 6 hours → hotel booked + rebooking offered."

    # ── Rule 4: Medium delay (2–6 hours) ──────────────────
    elif 2 <= delay_hours <= 6:
        voucher = issue_meal_voucher()
        actions_taken.append(voucher)
        recommendation = "Delay 2–6 hours → meal voucher issued."

        # Gold/Silver members get travel credit on top
        if membership in ("gold", "silver"):
            credit = offer_travel_credit()
            actions_taken.append(credit)
            recommendation += f" {membership.capitalize()} member → travel credit added."

    # ── Rule 5: Short delay (< 2 hours) ───────────────────
    elif delay_hours > 0 and delay_hours < 2:
        recommendation = "Delay under 2 hours → apology message sent. No compensation required."

    # ── Rule 6: No delay / unknown ────────────────────────
    else:
        recommendation = "No disruption detected or insufficient data. No action taken."

    # ── Bonus rule: Passenger explicitly asked for refund ──
    if passenger_request == "refund" and not cancelled:
        credit = offer_travel_credit()
        actions_taken.append(f"[Passenger requested refund] {credit}")
        recommendation += " Passenger requested refund → travel credit offered as alternative."

    print("\nActions taken:")
    for a in actions_taken:
        print(f"  ✓ {a}")
    print(f"\nFinal Recommendation:\n  {recommendation}")
    print("=" * 50)

    return {
        "recommendation": recommendation,
        "actions_taken": actions_taken,
    }


# ── Test cases ─────────────────────────────────────────────

if __name__ == "__main__":

    # Case 1: 3-hour delay, silver member
    case1 = {
        "delay_hours": 3,
        "cancelled": False,
        "has_connection": False,
        "membership": "silver",
        "passenger_request": "none",
    }

    # Case 2: 1-hour delay but passenger has a connecting flight
    case2 = {
        "delay_hours": 1,
        "cancelled": False,
        "has_connection": True,
        "membership": "standard",
        "passenger_request": "rebook",
    }

    # Case 3: Full cancellation
    case3 = {
        "delay_hours": 0,
        "cancelled": True,
        "has_connection": False,
        "membership": "gold",
        "passenger_request": "refund",
    }

    # Case 4: 8-hour delay — shows the rule failure (no check on membership for extra credit)
    case4 = {
        "delay_hours": 8,
        "cancelled": False,
        "has_connection": False,
        "membership": "gold",
        "passenger_request": "none",
    }

    for i, case in enumerate([case1, case2, case3, case4], 1):
        print(f"\n{'#'*50}")
        print(f"  TEST CASE {i}")
        print(f"{'#'*50}")
        reactive_agent(case)
