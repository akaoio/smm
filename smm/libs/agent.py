import frappe
from frappe import _
from . import utils, x, telegrambot, openai
import datetime
import copy

    
@frappe.whitelist()
def profile(**args):
    name = utils.find(args, "name")
    if not name:
        return

    agent = frappe.get_doc("Agent", name)
    provider = agent.provider

    clients = {
        "Telegram Bot": telegrambot,
        "X": x
    }
    client = clients.get(provider)

    response = client.profile(**args)

    # If type of response is dict and has json property
    data = response.json()

    # Always get nerd statistics.
    doc.update({
        "payload": {"text": text},
        "response": data,
        "response_status": response.status_code,
    })

    if response.status_code in [200, 201]:
        # The request is successful, now try to get the external id
        doc.update({"status": "Success"})
        if provider == "X":
            external_id = data.get("data").get("id")
        elif provider == "Telegram Bot":
            external_id = data.get("result").get("message_id")
        if external_id:
            doc.update({"external_id": external_id})
    else:
        doc.update({"status": "Failed"})

    doc.save()
    frappe.db.commit()

    return response