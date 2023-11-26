import frappe
from frappe import _
from . import utils, x, telegrambot


def selector(**args):
    name = utils.find(args, "name")
    if not name:
        return

    agent = frappe.get_doc("Agent", name)

    clients = {
        "Telegram Bot": telegrambot,
        "X": x
    }
    client = clients.get(agent.provider)
    if not client:
        return
    
    return client


@frappe.whitelist()
def profile(**args):
    client = selector(**args)
    return client.profile(**args)


@frappe.whitelist()
def refresh_access_token(**args):
    client = selector(**args)
    return client.refresh_access_token(**args)