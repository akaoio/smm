import frappe
import json
from frappe import _
from . import rss, x, facebook, telegrambot, openai, utils

clients = {
    "OpenAI": openai,
    "Telegram Bot": telegrambot,
    "X": x,
    "Facebook": facebook
}

provider = _("Feed Provider")

@frappe.whitelist()
# debug: bench execute smm.libs.feed.fetch --kwargs '{"name":"6868b18b03"}'
def fetch(**args):
    name = utils.find(args, "name")
    method = "fetch"
    
    if not name:
        msg = _("{0} name is empty").format(provider)
        frappe.msgprint(msg)
        return

    if not frappe.db.exists("Feed Provider", name):
        msg = _("{0} {1} does not exist").format(provider, name)
        frappe.msgprint(msg)
        return
    
    doc = frappe.get_doc("Feed Provider", name)

    owner = doc.owner or frappe.get_user().name

    client = rss if doc.type == "RSS" else clients.get(frappe.get_doc("API", doc.api).provider) if doc.type == "Crawler" else None
    
    if not client or not hasattr(client, method) or not callable(getattr(client, method)):
        return
    
    # Must returns {payload, response, feeds}
    process = getattr(client, method)(**doc.as_dict())
    if process:
        if process.get("payload") and process.get("response"):
            response = process.get("response")
            request = response.request
            payload = {
                "url": request.url,
                "body": request.body if hasattr(request, "body") else {},
                "params": request.params if hasattr(request, "params") else {},
                **process.get("payload")
            }
            doc.update({
                "payload": payload,
                "response": json.dumps({"content": response.content.decode("utf-8")}),
                "response_status": response.status_code
            })
        if process.get("feeds") is not None and len(process.get("feeds")) > 0:
            doc.update({"feeds": json.dumps(process.get("feeds"), indent=4)})
            if not doc.virtual:
                for feed in process.get("feeds"):
                    # Check if the feed already exists before inserting
                    if not frappe.db.exists({"doctype":"Feed", **feed}):
                        frappe.get_doc({
                            "owner": owner,
                            "doctype": "Feed",
                            "provider": name,
                            **feed
                        }).insert()
                        frappe.db.commit()
    
        doc.save()
        frappe.db.commit()
