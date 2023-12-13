import frappe
import datetime
from ..libs import feed


@frappe.whitelist()
def fetch_all():
    feed_providers = frappe.db.get_list("Feed Provider", fields=["name", "virtual", "duration", "fetched"], order_by="fetched asc")
    current_datetime = datetime.datetime.strptime(frappe.utils.now(), "%Y-%m-%d %H:%M:%S.%f")
    for feed_provider in feed_providers:
        # Convert duration to timedelta
        duration = datetime.timedelta(seconds=feed_provider.duration) if feed_provider.duration else datetime.timedelta()
        # Get next fetch datetime
        next_fetch = feed_provider.fetched + duration if feed_provider.fetched else None
        # If never fetched before or next fetch datetime is less than or equal to current datetime, fetch
        if next_fetch is None or next_fetch <= current_datetime:
            feed.fetch(name=feed_provider.name)
            # Update fetched datetime
            frappe.db.set_value("Feed Provider", feed_provider.name, "fetched", datetime.datetime.now())
            frappe.db.commit()