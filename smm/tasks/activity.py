import frappe
from ..libs import activity
import datetime


@frappe.whitelist()
def process_plans():
    # Get current date and time using Frappe Utils then convert it to timedelta
    current_datetime = datetime.datetime.strptime(frappe.utils.now(), "%Y-%m-%d %H:%M:%S.%f")
    current_date = current_datetime.date()
    current_time = current_datetime.time()

    # network_activity_plans = frappe.db.sql(
    #     """
    #         SELECT `name`
    #         FROM `tabNetwork Activity Plan`
    #         WHERE
    #             `enabled` IS TRUE AND
    #             (
    #                 `start_date` IS NULL OR
    #                 (
    #                     `start_date` <= %(current_date)s AND
    #                     (
    #                         `start_time` IS NULL OR
    #                         (
    #                             (`start_time` <= %(current_time)s AND `start_date` = %(current_date)s) OR
    #                             `start_date` < %(current_date)s
    #                         )
    #                     )
    #                 )
    #             ) AND
    #             (
    #                 `end_date` IS NULL OR
    #                 (
    #                     `end_date` >= %(current_date)s AND
    #                     (
    #                         `end_time` IS NULL OR
    #                         (
    #                             (`end_time` >= %(current_time)s AND `end_date` = %(current_date)s) OR
    #                             `end_date` > %(current_date)s
    #                         )
    #                     )
    #                 )
    #             )
    #         ORDER BY `start_date` ASC, `start_time` ASC
    #         LIMIT 3
    #     """,
    #     {"current_date": current_date, "current_time": current_time},
    #     as_dict=True
    # )

    doctype = frappe.qb.DocType("Network Activity Plan")

    network_activity_plans = frappe.qb.from_(doctype).select("name").distinct().where(
        (doctype.enabled == True) &
        (
            (doctype.start_date == None) |
            (
                (doctype.start_date <= current_date) &
                (
                    (doctype.start_time == None) |
                    (
                        ((doctype.start_time <= current_time) & (doctype.start_date == current_date)) |
                        (doctype.start_date < current_date)
                    )
                )
            )
        ) &
        (
            (doctype.end_date == None) |
            (
                (doctype.end_date >= current_date) &
                (
                    (doctype.end_time == None) |
                    (
                        ((doctype.end_time >= current_time) & (doctype.end_date == current_date)) |
                        (doctype.end_date > current_date)
                    )
                )
            )
        )
    ).orderby(doctype.start_date, doctype.start_time).limit(3).run(as_dict=True)

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
            ["enabled", "=", True],
            ["status", "=", "Pending"],
            ["content", "is", "not set"]
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
            ["enabled", "=", True],
            ["status", "=", "Pending"],
            ["content", "is", "set"]
        ],
        fields=["name", "agent", "content", "schedule"],
        order_by="schedule asc",
        limit_page_length=3
    )

    for item in network_activities:
        activity.cast(**item)

    return network_activities
