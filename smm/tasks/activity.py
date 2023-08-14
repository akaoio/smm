import frappe
from ..libs import activity
import datetime


@frappe.whitelist()
def generate_activities():
    # Get current date and time using Frappe Utils then convert it to timedelta
    current_datetime = datetime.datetime.strptime(frappe.utils.now(), "%Y-%m-%d %H:%M:%S.%f")
    start_datetime = current_datetime - datetime.timedelta(hours=1)
    end_datetime = current_datetime + datetime.timedelta(hours=1)

    network_activity_plans = frappe.db.get_list(
        "Network Activity Plan",
        filters=[
            ["schedule", ">=", start_datetime],
            ["schedule", "<=", end_datetime],
            ["status", "=", "Pending"],
            ["content", "=", ""]
        ],
        fields=["name", "schedule"],
        order_by="schedule asc",
        limit_page_length=3
    )

    for item in network_activity_plans:
        activity.generate_activity(name=item.name)

    return network_activity_plans


@frappe.whitelist()
def process_activities():
    # Get current date and time using Frappe Utils then convert it to timedelta
    current_datetime = datetime.datetime.strptime(frappe.utils.now(), "%Y-%m-%d %H:%M:%S.%f")
    start_datetime = current_datetime - datetime.timedelta(hours=1)
    end_datetime = current_datetime + datetime.timedelta(hours=1)

    network_activities = frappe.db.get_list(
        "Network Activity",
        filters=[
            ["schedule", ">=", start_datetime],
            ["schedule", "<=", end_datetime],
            ["status", "=", "Pending"],
            ["content", "=", ""]
        ],
        fields=["name", "schedule"],
        order_by="schedule asc",
        limit_page_length=3
    )

    for item in network_activities:
        activity.generate_content(name=item.name)

    return network_activities


@frappe.whitelist()
def cast_activities():
    # Get current date and time using Frappe Utils then convert it to timedelta
    current_datetime = datetime.datetime.strptime(frappe.utils.now(), "%Y-%m-%d %H:%M:%S.%f")
    start_datetime = current_datetime - datetime.timedelta(hours=1)
    network_activities = frappe.db.get_list(
        "Network Activity",
        filters=[
            ["schedule", ">=", start_datetime],
            ["schedule", "<=", current_datetime],
            ["status", "=", "Pending"],
            ["content", "!=", ""]
        ],
        fields=["name", "agent", "content", "schedule"],
        order_by="schedule asc",
        limit_page_length=3
    )

    for item in network_activities:
        activity.cast(item)

    return network_activities
