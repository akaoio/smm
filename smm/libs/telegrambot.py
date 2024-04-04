from urllib.parse import urlencode

import frappe
import requests
from frappe import _

from . import utils


class TelegramBot:
    def __init__(self, token):
        if not token:
            frappe.throw(_("Telegram API is required"))
            return
        self.base_url = f"https://api.telegram.org/bot{token}"

    def request(self, method="POST", url=None, endpoint=None, params={}, data={}, json={}, headers=None, request=True,files=None):
        url = url or self.base_url + endpoint

        if headers is None:
            headers = {
                "Content-Type": "application/json",
        }

        # Complete URL with encoded parameters
        if method == "GET" and not request:
            return url + "?" + urlencode(params)
        if request:
            return requests.request(method, url, params=params, data=data, json=json, headers=headers, files=files)

    def send_message(self, chat_id: str, text: str, extra_payload={}):
        """
        Send text to group/channel without image
        """
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        payload.update(extra_payload)
        response = self.request(endpoint="/sendMessage", params=payload)
        return response

    def send_photo(self, chat_id: str, text: str, image_path: str, extra_payload={}):
        """
        Send photo to group/channel with image. 
        Now "text" is caption of image.
        """
        payload = {
            "chat_id": chat_id,
            "caption": text,
        }
        payload.update(extra_payload)
        files = {"photo": open(image_path, "rb")}
        response = self.request(
            endpoint="/sendPhoto", headers={}, data=payload, files=files)
        return response


@frappe.whitelist()
def profile(**args):
    name = utils.find(args, "name")
    agent = utils.find(args, "agent") or frappe.get_doc("Agent", name)
    api = frappe.get_doc("API", agent.get("api"))
    token = api.get_password("token") or None
    alias = agent.get("alias")
    # Check if alias starts with '@', if not, add it
    if alias and not alias.startswith("@"):
        alias = "@" + alias
    chat_id = agent.get("uid") or alias
    client = TelegramBot(token=token)

    response = client.request(method="GET", endpoint="/getChat", params={"chat_id": alias})

    data = response.json()

    if not data.get("ok"):
        if data.get("description"):
            msg = _(data.get("description"))
            frappe.msgprint(msg)
        return response

    profile = response.json().get("result")
    
    display_name = profile.get("title") if profile.get("type") in ["group", "supergroup", "channel"] else f"{profile.get('first_name')} {profile.get('last_name')}" if profile.get("first_name") and profile.get("last_name") else profile.get("first_name") if profile.get("first_name") else profile.get("last_name") if profile.get("last_name") else profile.get("username")
    description = profile.get("description") if profile.get("type") in ["group", "supergroup", "channel"] else profile.get("bio") if profile.get("bio") else None
    picture_id = profile.get("photo").get("big_file_id") if profile.get("photo") else None
    picture_url = None
    if picture_id:
        picture = client.request(method="GET", endpoint="/getFile", params={"file_id": picture_id})
        picture_url = client.request(method="GET", endpoint="/" + picture.json().get("result").get("file_path"), request=False)
    
    # Get chat members
    members = client.request(method="GET", endpoint="/getChatMembersCount", params={"chat_id": chat_id})
    members = members.json().get("result")
    audience_size = members if members else None
    
    if profile.get("id") and display_name:
        frappe.get_doc("Agent", name).update({"uid": profile.get("id"), "display_name": display_name, "alias": profile.get("username"), "description": description, "picture": picture_url, "audience_size": audience_size}).save()
        frappe.db.commit()
    
    return response


@frappe.whitelist()
def send(**args):
    name = utils.find(args, "name")
    agent = utils.find(args, "agent") or frappe.get_doc("Agent", name)
    text = utils.find(args, "text")
    image_path = utils.find(args, "image_path")
    api = frappe.get_doc("API", agent.get("api"))
    token = api.get_password("token") or None
    alias = agent.get("alias")
    # Check if alias starts with '@', if not, add it
    if alias and not alias.startswith("@"):
        alias = "@" + alias
    chat_id = agent.get("uid") or alias
    linked_external_id = utils.find(args, "linked_external_id")

    client = TelegramBot(token=token)

    params = {"chat_id": chat_id, "text": text}

    if linked_external_id:
        params.update(
            {"extra_payload":{"reply_to_message_id": linked_external_id}}
        )
    if image_path:
        params["image_path"] = image_path
        response = client.send_photo(**params)
    else:
        response = client.send_message(**params)
    return response