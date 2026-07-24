import json

with open("data/airline_data.json", "r") as file:
    DATA = json.load(file)

def check_available_flights(case_description):

    if "10 hours" in case_description:
        return DATA["flights"]["10_hours"]

    elif "6 hours" in case_description:
        return DATA["flights"]["6_hours"]

    elif "4 hours" in case_description:
        return DATA["flights"]["4_hours"]

    elif "2 hours" in case_description:
        return DATA["flights"]["2_hours"]

    return []

def issue_meal_voucher():

    return DATA["compensation"]["meal_voucher"]["message"]

def offer_travel_credit():

    return DATA["compensation"]["travel_credit"]["message"]
def notify_hotel():

    return DATA["hotels"]

TOOLS = {
    "check_available_flights": check_available_flights,
    "issue_meal_voucher": issue_meal_voucher,
    "offer_travel_credit": offer_travel_credit,
    "notify_hotel": notify_hotel,
}