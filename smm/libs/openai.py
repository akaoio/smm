import frappe
from frappe import _
import random
import json
import requests
from ..libs import utils


class OpenAI:
    def __init__(self, token=None):
        self.base_url = "https://api.openai.com"
        self.token = token

    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def request(self, method="POST", url=None, endpoint=None, data={}):
        url = url or self.base_url + endpoint
        response = requests.request(
            method,
            url,
            headers=self.headers(),
            data=json.dumps(data)
        )
        return response


@frappe.whitelist()
def generate_content(**args):
    mechanism = utils.find(args, "name") or utils.find(args, "mechanism")

    doc = frappe.get_doc("Content Mechanism", mechanism)
    if doc.enabled == 0:
        frappe.msgprint(_(f"Content Mechanism {mechanism} is disabled."))
        return

    feeds = {}
    prompts = []

    # If given a linked Network Activity, try to get Content of that Activity and generate responsive Contents to it.
    activity = utils.find(args, "activity")
    if activity:
        linked_activity_doc = frappe.get_doc("Network Activity", activity)
        if linked_activity_doc.content:
            linked_content_doc = frappe.get_doc("Content", linked_activity_doc.content)
            if linked_content_doc.description:
                feeds.update({linked_content_doc.name: {"title": linked_content_doc.title, "description": linked_content_doc.description}})

    length = doc.length

    feed_provider_list = doc.feed_providers

    feed_list = doc.feeds

    prompt_list = doc.prompts

    for item in feed_provider_list:
        docs = frappe.db.get_list("Feed", filters={"provider": item.feed_provider}, fields=["name", "title", "description"], order_by="creation desc", limit_start=0, limit_page_length=item.limit)
        for doc in docs:
            feeds.update({doc.name: {"title": doc.title, "description": doc.description}})

    for item in feed_list:
        doc = frappe.get_doc("Feed", item.feed)
        feeds.update({doc.name: {"title": doc.title, "description": doc.description}})

    for item in prompt_list:
        doc = frappe.get_doc("Prompt", item.prompt)
        prompts.append({"role": "user", "content": doc.description})

    if len(feeds) > 0:
        prompts.append({"role": "user", "content": json.dumps({"DATA": feeds})})

    # Temporarily get random API. This needs to be fixed.
    apis = frappe.db.get_list("API", filters={"provider": "OpenAI"})
    if (len(apis) > 0):
        api = random.choice(apis).name
        doc = frappe.get_doc("API", api)
        token = doc.get_password("token") if doc.token else None

    if not token:
        return

    client = OpenAI(token)

    data = {
        "model": "gpt-3.5-turbo",
        "messages": prompts,
        "functions": [
            {
                "name": "generate_content",
                "description": "Create a content from given prompts and DATA. Returns `title` and `description`.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "The shortest version of the content."
                        },
                        "description": {
                            "type": "string",
                            "description": "Content Description." + f" Maximum number of characters is {length}." if length and length > 0 else ""
                        },
                    },
                    "required": ["title", "description"]
                }
            }
        ]
    }

    response = client.request(endpoint="/v1/chat/completions", data=data)
    data = response.json()
    error = data.get("error") or {}
    message = error.get("message") or {}

    if response.status_code != 200 and message:
        frappe.msgprint(_(message))
        return response

    if response.status_code == 200:
        message = random.choice(data.get("choices")).get("message").get("function_call").get("arguments")
        message = json.loads(message)
        title = message.get("title")
        title = utils.remove_mentions(title)
        title = utils.remove_quotes(title)
        description = message.get("description")
        description = utils.remove_mentions(description)
        description = utils.remove_quotes(description)
        doc = frappe.get_doc({
            "doctype": "Content",
            "mechanism": mechanism,
            "title": title,
            "description": description if len(description) > len(title) else title,
        })
        doc.insert()
        frappe.db.commit()
        return doc
