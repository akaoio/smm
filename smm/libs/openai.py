import io
import json as JSON
import random

import frappe
import PIL
import requests
from frappe import _

from ..libs import utils


class OpenAI:
    def __init__(self, token=None, authorization_type="Bearer", content_type="json"):
        self.base_url = "https://api.openai.com"
        self.token = token
        self.authorization_type = authorization_type
        self.content_type = content_type
    
    def bearer(self):
        return f"Bearer {self.token}"

    def basic(self):
        return self.bearer()
        # data = f"{self.client_id}:{self.client_secret}" if self.client_id and self.client_secret else f"{self.consumer_id}:{self.consumer_secret}" if self.consumer_id and self.consumer_secret else None
        # return f"Basic {base64.b64encode(data.encode('utf-8')).decode('utf-8')}"

    def authorization_header(self, type=None):
        type = type or self.authorization_type
        return self.bearer() if type == "Bearer" else self.basic() if type == "Basic" else None

    def content_type_header(self, type=None):
        type = type or self.content_type
        return "application/json" if type == "json" else "application/x-www-form-urlencoded" if type == "urlencoded" else "multipart/form-data" if type == "form" else None

    def headers(self, authorization_type=None, content_type=None, headers={}):
        authorization_type = authorization_type or headers.get("authorization_type") or self.authorization_type
        content_type = content_type or headers.get("content_type") or self.content_type
        return {
            "Authorization": self.authorization_header(authorization_type),
            "Content-Type": self.content_type_header(content_type)
        }

    def request(self, method="POST", url=None, endpoint=None, json={}, data={}, headers={}, **args):
        url = url or self.base_url + endpoint
        headers = self.headers(headers=headers)
        if utils.find(args, "files"):
            del headers["Content-Type"] # If files present, let requests library handle content type
        if headers.get("Content-Type") == "application/json":
            data = JSON.dumps(data)
            json = JSON.dumps(json)
        
        return requests.request( method, url, headers=headers, data=data, json=json, **args)

def join_data(args):
    title = utils.find(args, "title")
    description = utils.find(args, "description")
    data = title if title else ""
    data += f". {description}" if description else ""
    return data if len(data) > 0 else None


@frappe.whitelist()
def generate_content(**args):
    mechanism = utils.find(args, "name") or utils.find(args, "mechanism")
    
    if not frappe.db.exists("Content Mechanism", mechanism):
        frappe.msgprint(_("{0} {1} does not exist").format(_("Content Mechanism"), mechanism))
        return
    
    doc = frappe.get_doc("Content Mechanism", mechanism)
    
    owner = doc.owner or frappe.get_user().name
    
    if doc.enabled == 0:
        frappe.msgprint(_("{0} {1} is disabled").format(_("Content Mechanism"), mechanism))
        return
    
    feeds = []
    feed_images = []
    prompts = []

    # If given a linked Network Activity, try to get Content of that Activity and generate responsive Contents to it.
    activity = utils.find(args, "activity")
    if activity:
        linked_activity_doc = frappe.get_doc("Network Activity", activity)
        if linked_activity_doc.content:
            linked_content_doc = frappe.get_doc("Content", linked_activity_doc.content)
            content = join_data(linked_content_doc)
            if content and content not in feeds:
                feeds.append(content)

    generate_text = doc.generate_text
    generate_image = doc.generate_image
    generate_image_variation = doc.generate_image_variation
    length = doc.length
    description_to_image = doc.description_to_image
    size = doc.size or "512x512"
    style = doc.style.lower() if doc.style else "natural"
    images = doc.images
    feed_provider_list = doc.feed_providers
    feed_list = doc.feeds
    prompt_list = doc.prompts
    
    for item in feed_provider_list:
        feed_provider = frappe.get_doc("Feed Provider", item.feed_provider)
        # If feed provider is virtual, try to get feeds from the `feeds` field, which is a JSON array, then append to `feeds` list.
        # Else get feeds from the database.
        docs = JSON.loads(feed_provider.feeds) if feed_provider.feeds and feed_provider.virtual else frappe.db.get_list("Feed", filters={"provider": item.feed_provider}, fields=["name", "title", "description", "image"], order_by="creation desc", limit_start=0, limit_page_length=item.limit)
        if len(docs) > item.limit: docs = random.sample(docs, item.limit)

        for doc in docs:
            content = join_data(doc)
            if content and content not in feeds: feeds.append(content)
            if doc.image: feed_images.append(frappe.utils.get_url(doc.image))
    for item in feed_list:
        doc = frappe.get_doc("Feed", item.feed)
        content = join_data(doc)
        if content and content not in feeds: feeds.append(content)

    for item in prompt_list:
        doc = frappe.get_doc("Prompt", item.prompt)
        prompts.append(doc.description)

    if len(feeds) > 0:
        prompts.append(JSON.dumps({"DATA": feeds}))

    # Temporarily get random API. This needs to be fixed.
    apis = frappe.db.get_list("API", filters={"provider": "OpenAI"})
    if (len(apis) > 0):
        api = random.choice(apis).name
        doc = frappe.get_doc("API", api)
        token = doc.get_password("token") if doc.token else None

    if not token:
        return

    client = OpenAI(token)
    
    new_doc = frappe.get_doc({
        "owner": owner,
        "doctype": "Content",
        "mechanism": mechanism
    })
    
    description = None
    
    def save_image(url):
        file = requests.get(url=url)
        # Convert file content to PNG using PIL and io
        content = to_png(file.content)
        random_name = frappe.utils.random_string(24) + ".png"
        if not new_doc.name:
            new_doc.insert()
            frappe.db.commit()
        check_folder(name="SMM")
        file = frappe.utils.file_manager.save_file(random_name, content, dt="Content", dn=new_doc.name, df="image", folder="Home/SMM", decode=False, is_private=False)
        new_doc.update({
            "image": file.get("file_url")
        })
        new_doc.save()
        frappe.db.commit()
    
    if generate_text:
        messages = []
        for prompt in prompts:
            messages.append({"role": "user", "content": prompt})
        for url in feed_images:
            messages.append(
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": url}}],
                }
            )

        data = {
            # "model": "gpt-3.5-turbo",
            "model": "gpt-4-turbo",
            "messages": messages,
            "n": 1,
            "tools": [
                {
                    "type": "function",
                    "function": {
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
                }
            ],
            "tool_choice": {
                "type": "function",
                "function": {
                    "name": "generate_content"
                }
            }
        }

        response = client.request(endpoint="/v1/chat/completions", data=data)

        data = response.json()
        error = data.get("error") or {}
        message = error.get("message") or {}
    
        if response.status_code != 200 and message:
            frappe.msgprint(_(message))
    
        if response.status_code == 200:
            choice = random.choice(data.get("choices"))
            message = choice.get("message").get("tool_calls")[0].get("function").get("arguments")
            message = JSON.loads(message)
            title = message.get("title")
            title = utils.remove_mentions(title)
            title = utils.remove_quotes(title)
            description = message.get("description")
            description = utils.remove_mentions(description)
            description = utils.remove_quotes(description)
            description = description if len(description) > len(title) else title
            new_doc.update({
                "title": title,
                "description": description
            })
            new_doc.insert()
            frappe.db.commit()
            if len(feed_images) > 0:
                save_image(random.choice(feed_images))

    if generate_image:
        prompt = description if description_to_image and description and len(description) > 0 else ". ".join(prompts) if len(prompts) > 0 else None
        if not prompt:
            frappe.msgprint(_("Prompt is required to generate image."))
            pass
        data = {
            "model": "dall-e-2",
            "prompt": prompt,
            "response_format": "url", # Must be "url" or "b64_json"
            "size": size, # 256x256, 512x512, 1024x1024
            "quality": "standard",
            "style": style, # Must be "natural" or "vivid"
            "n": 1
        }
        
        response = client.request(endpoint="/v1/images/generations", data=data)
        data = response.json()
        error = data.get("error") or {}
        message = error.get("message") or {}
        
        if response.status_code != 200 and message:
            frappe.msgprint(_(message))
    
        if response.status_code == 200:
            data = random.choice(data.get("data"))
            save_image(data.get("url"))
            
    
    if generate_image_variation:
        image = frappe.get_doc("File", random.choice(images).image)
        file = frappe.utils.file_manager.get_file(image.file_name)
        file_name = file[0]
        file_content = file[1]

        content = to_png(file_content)
        files = {'image': content}
        
        data = {
            "model": "dall-e-2",
            "image": content,
            "response_format": "url", # Must be "url" or "b64_json"
            "size": size, # 256x256, 512x512, 1024x1024
            "n": 1
        }

        response = client.request(endpoint="/v1/images/variations", data=data, files=files)
        data = response.json()
        error = data.get("error") or {}
        message = error.get("message") or {}

        if response.status_code != 200 and message:
            frappe.msgprint(_(message))
        
        if response.status_code == 200:
            data = random.choice(data.get("data"))
            save_image(data.get("url"))
    
    return new_doc if new_doc.name else True


def check_folder(**args):
    name = utils.find(args, "name") or ""
    if not frappe.db.exists({"doctype": "File", "name": f"Home/{name}", "file_name": name, "is_folder": True}):
        folder = frappe.get_doc({
            "doctype": "File",
            "file_name": name,
            "is_folder": True,
            "folder": "Home"
        })
        folder.insert()
        frappe.db.commit()
        return folder


def to_png(content):
    content = io.BytesIO(content)
    content = PIL.Image.open(content)
    buffer = io.BytesIO()
    content.save(buffer, "PNG")
    buffer.seek(0) # Ensure pointer is at the start of the file
    return buffer.getvalue()