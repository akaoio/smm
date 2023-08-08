import frappe
from ..libs import twitter as client, utils


@frappe.whitelist()
def refresh_tokens():
    list = frappe.db.get_all("Agent", filters={"provider": "Twitter"}, order_by="modified asc")
    for item in list:
        doc = frappe.get_doc("Agent", item.name)
        duration = utils.duration(doc.get("modified"))
        if (duration >= 5000):
            client.refresh_token(name=doc.name)
