import frappe
from frappe import _
import random
import json
import requests
import base64
from ..libs import utils


class OpenAI:
    def __init__(self, token=None):
        self.base_url = "https://api.openai.com"
        self.token = token

    def headers(self, headers={}):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            **headers
        }

    def request(self, method="POST", url=None, endpoint=None, data={}, headers={}, **args):
        url = url or self.base_url + endpoint
        
        if headers.get("Content-Type") == "application/json":
            data =json.dumps(data)

        response = requests.request(
            method,
            url,
            headers=self.headers(headers),
            data=data,
            **args
        )
        return response

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

    length = doc.length
    generate_text = doc.generate_text
    generate_image = doc.generate_image
    generate_image_variation = doc.generate_image_variation
    images = doc.images
    feed_provider_list = doc.feed_providers
    feed_list = doc.feeds
    prompt_list = doc.prompts
    
    for item in feed_provider_list:
        feed_provider = frappe.get_doc("Feed Provider", item.feed_provider)
        # If feed provider is virtual, try to get feeds from the `feeds` field, which is a JSON array, then append to `feeds` list.
        # Else get feeds from the database.
        docs = json.loads(feed_provider.feeds) if feed_provider.feeds and feed_provider.virtual else frappe.db.get_list("Feed", filters={"provider": item.feed_provider}, fields=["name", "title", "description"], order_by="creation desc", limit_start=0, limit_page_length=20)
        if item.limit and len(docs) > item.limit: docs = random.sample(docs, item.limit)
        for doc in docs:
            content = join_data(doc)
            if content and content not in feeds: feeds.append(content)

    for item in feed_list:
        doc = frappe.get_doc("Feed", item.feed)
        content = join_data(doc)
        if content and content not in feeds: feeds.append(content)

    for item in prompt_list:
        doc = frappe.get_doc("Prompt", item.prompt)
        prompts.append(doc.description)

    if len(feeds) > 0:
        prompts.append(json.dumps({"DATA": feeds}))

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
    
    if generate_text:
        messages = []
        for prompt in prompts:
            messages.append({"role": "user", "content": prompt})
        data = {
            "model": "gpt-3.5-turbo",
            # "model": "gpt-4-turbo",
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
            message = json.loads(message)
            title = message.get("title")
            title = utils.remove_mentions(title)
            title = utils.remove_quotes(title)
            description = message.get("description")
            description = utils.remove_mentions(description)
            description = utils.remove_quotes(description)
            new_doc.update({
                "title": title,
                "description": description if len(description) > len(title) else title
            })
            new_doc.insert()
            frappe.db.commit()
    
    if generate_image:
        data = {
            "model": "dall-e-2",
            "prompt": ". ".join(prompts) if len(prompts) > 0 else "",
            "response_format": "b64_json", # Must be "url" or "b64_json"
            "size": "256x256", # 256x256, 512x512, 1024x1024
            "quality": "standard",
            "style": "natural", # Must be "natural" or "vivid"
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
            content = data.get("b64_json")
            random_name = frappe.utils.random_string(24) + ".png"
            if not new_doc.name:
                new_doc.insert()
                frappe.db.commit()
            check_folder(name="SMM")
            file = frappe.utils.file_manager.save_file(random_name, content, dt="Content", dn=new_doc.name, df="image", folder="Home/SMM", decode=True, is_private=False)
            new_doc.update({
                "image": file.get("file_url")
            })
            new_doc.save()
            frappe.db.commit()
            
    
    if generate_image_variation:
        image = frappe.get_doc("File", random.choices(images)[0].image)
        file_path = frappe.utils.file_manager.get_file_path(image.file_name)
        # print("PATH", file_path)
        file = frappe.utils.file_manager.get_file(image.file_name)
        file_name = file[0]
        file_content = file[1]
        
        # print("FILE", file)
        # files = {'image': (file_path, file, 'image/png')}
        # files = {'image': (file_path, file)}
        # convert to base64 string

        # file_content = base64.b64encode(file.read())
        

        # Create the JSON payload with the 'image' property
        payload = {'image': file_content}
            
        data = {
            "model": "dall-e-2",
            "image": file,
            "response_format": "b64_json", # Must be "url" or "b64_json"
            "size": "256x256", # 256x256, 512x512, 1024x1024
            "n": 1
        }

        response = client.request(endpoint="/v1/images/variations", headers={"Content-Type": "multipart/form-data"}, data=data, json=payload)
        print(response.status_code, response.content)
        return

        data = response.json()
        error = data.get("error") or {}
        message = error.get("message") or {}

        print("DATA", data)
        
        if response.status_code != 200 and message:
            frappe.msgprint(_(message))
        
        if response.status_code == 200:
            data = random.choice(data.get("data"))
            content = data.get("b64_json")
            random_name = frappe.utils.random_string(24) + ".png"
            if not new_doc.name:
                new_doc.insert()
                frappe.db.commit()
            check_folder(name="SMM")
            file = frappe.utils.file_manager.save_file(random_name, content, dt="Content", dn=new_doc.name, df="image", folder="Home/SMM", decode=True, is_private=False)
            new_doc.update({
                "image": file.get("file_url")
            })
            new_doc.save()
            frappe.db.commit()
        
    
    return True


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

# @frappe.whitelist()
# def generate_image_variations(**args):
    