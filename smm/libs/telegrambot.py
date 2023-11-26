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
def profile(**args):
    name = utils.find(args, "name")
    agent = utils.find(args, "agent") or frappe.get_doc("Agent", name)
    api = frappe.get_doc("API", agent.get("api"))
    token = api.get_password("token") or None
    client = TelegramBot(token=token)
    response = client.request(endpoint="/getChat", params={"chat_id": agent.get("alias")})
    profile = response.json().get("data")
    display_name = profile.get("title") if profile.get("type") in ["group", "supergroup", "channel"] else f"{profile.get('first_name')} {profile.get('last_name')}" if profile.get("first_name") and profile.get("last_name") else profile.get("first_name") if profile.get("first_name") else profile.get("last_name") if profile.get("last_name") else profile.get("username")
    picture_file = profile.get("photo").get("big_file_id") if profile.get("photo") else None
    picture_url = None
    if picture_file:
        picture = client.request(endpoint="/getFile", params={"file_id": picture_file})
        picture_url = client.request(method="GET", url=picture.json().get("data").get("file_path"), request=False)
    frappe.get_doc("Agent", name).update({"uid": profile.get("id"), "display_name": display_name, "alias": profile.get("username"), "picture": picture_url}).save()
    frappe.db.commit()


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
