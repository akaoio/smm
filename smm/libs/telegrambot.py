import frappe
from frappe import _
import requests
from urllib.parse import urlencode
from . import utils


class TelegramBot:
    def __init__(self, token):
        if not token:
            frappe.throw(_("Telegram API is required"))
            return
        self.base_url = f"https://api.telegram.org/bot{token}"

    def request(self, method="POST", url=None, endpoint=None, params={}, data={}, json={}, headers={}, request=True):
        url = url or self.base_url + endpoint

        headers = {
            "Content-Type": "application/json",
            **headers
        }

        # Complete URL with encoded parameters
        if method == "GET" and not request:
            return url + "?" + urlencode(params)
        if request:
            return requests.request(method, url, params=params, data=data, json=json, headers=headers)


@frappe.whitelist()
def send(**args):
    name = utils.find(args, "name")
    agent = utils.find(args, "agent") or frappe.get_doc("Agent", name)
    text = utils.find(args, "text")
    api = frappe.get_doc("API", agent.get("api"))
    token = api.get_password("token") or None
    alias = agent.get("alias")
    # Check if alias starts with '@', if not, add it
    if alias and not alias.startswith("@"):
        alias = "@" + alias
    linked_external_id = utils.find(args, "linked_external_id")

    client = TelegramBot(token=token)

    params = {"chat_id": alias, "text": text}

    if linked_external_id:
        params.update({"reply_to_message_id": linked_external_id})

    response = client.request(
        endpoint="/sendMessage",
        params=params,
    )
    return response
