def check_available_flights():
    return [
        "Flight MS245 - 2 hours later",
        "Flight MS320 - Tomorrow 8:00 AM"
    ]


def issue_meal_voucher():
    return "Meal voucher issued successfully."


def offer_travel_credit():
    return "$150 travel credit offered."


def notify_hotel():
    return "Hotel accommodation booked."


TOOLS = {
    "check_available_flights": check_available_flights,
    "issue_meal_voucher": issue_meal_voucher,
    "offer_travel_credit": offer_travel_credit,
    "notify_hotel": notify_hotel,
}
