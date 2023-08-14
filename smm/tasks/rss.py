import frappe
from ..libs import rss as client, utils


@frappe.whitelist()
def fetch_all():
    feed_providers = frappe.db.get_list("Feed Provider", fields=["name", "fetched"], order_by="fetched asc")
    for feed_provider in feed_providers:
        duration = utils.duration(feed_provider.fetched, unit="minute")
        if (duration == None or duration > 360):
            client.fetch(name=feed_provider.name)