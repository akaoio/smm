import base64
import json

import frappe
from frappe import _

from . import crawler, facebook, openai, rss, telegrambot, utils, x

clients = {
    "OpenAI": openai,
    "Telegram Bot": telegrambot,
    "X": x,
    "Facebook": facebook
}

feed_provider_locale = _("Feed Provider")

@frappe.whitelist()
# debug: bench execute smm.libs.feed.fetch --kwargs '{"name":"6868b18b03"}'
def fetch(**args):
    name = utils.find(args, "name")
    method = "fetch"
    
    if not name:
        msg = _("{0} name is empty").format(feed_provider_locale)
        frappe.msgprint(msg)
        return

    if not frappe.db.exists("Feed Provider", name):
        msg = _("{0} {1} does not exist").format(feed_provider_locale, name)
        frappe.msgprint(msg)
        return
    
    doc = frappe.get_doc("Feed Provider", name)
    if not doc.enabled:
        return
    
    owner = doc.owner or frappe.get_user().name
    
    agent = frappe.get_doc("Agent", doc.agent) if doc.agent else None
    
    api = frappe.get_doc("API", agent.api) if hasattr(agent, "api") else frappe.get_doc("API", doc.api) if doc.api else None
        
    client = rss if doc.type == "RSS" else crawler if doc.type == "Crawler" and hasattr(api, "provider") else None
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
                    file_data = base64.b64decode(feed.pop("image"))
                    # Check if the feed already exists before inserting
                    if not frappe.db.exists({"doctype":"Feed", **feed}):
                        new_doc = frappe.get_doc({
                            "owner": owner,
                            "doctype": "Feed",
                            "provider": name,
                            **feed
                        }).insert()
                        frappe.db.commit()
                        save_image(file_data, new_doc)
    # Update fetched datetime
    doc.update({"fetched": frappe.utils.now()})
    doc.save()
    frappe.db.commit()
    return True


def save_image(content, doc):
    # Convert file content to PNG using PIL and io
    content = utils.to_png(content)
    random_name = frappe.utils.random_string(24) + ".png"
    utils.check_folder(name="SMM")
    file = frappe.utils.file_manager.save_file(
        random_name,
        content,
        dt="Feed",
        dn=doc.name,
        df="image",
        folder="Home/SMM",
        decode=False,
        is_private=False,
    )
    doc.update({"image": file.get("file_url")})
    doc.save()
    frappe.db.commit()
