import frappe
from frappe import _
from . import utils, x, facebook, telegrambot, openai


def call(method, **args):
    name = utils.find(args, "name")
    
    if not name:
        return

    provider = utils.find(args, "provider") if not frappe.db.exists("Agent", name) else frappe.get_doc("Agent", name).provider
    
    if not provider:
        return
    
    clients = {
        "OpenAI": openai,
        "Telegram Bot": telegrambot,
        "X": x,
        "Facebook": facebook
    }
    client = clients.get(provider)
    
    if not client:
        return
    
    # Check if client has method and method is a function
    if hasattr(client, method) and callable(getattr(client, method)):
        return getattr(client, method)(**args)
    
    return client


@frappe.whitelist()
def authorize(**args):
    return call("authorize", **args)


@frappe.whitelist()
def refresh_access_token(**args):
    return call("refresh_access_token", **args)


@frappe.whitelist()
def profile(**args):
    return call("profile", **args)