import frappe
from ..libs import rss as client, utils


@frappe.whitelist()
def fetch_all():
    list = frappe.db.get_all("Feed Provider", order_by="fetched asc")
    for item in list:
        doc = frappe.get_doc("Feed Provider", item.name)
        duration = utils.duration(doc.get("fetched"), unit="minute")
        if (duration == None or duration > 3600):
            client.fetch(name=doc.name)
