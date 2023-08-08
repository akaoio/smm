import frappe
from frappe import _
import requests
import re
import html
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs
from . import utils


@frappe.whitelist()
def fetch(**args):
    name = utils.find(args, "name")
    if not name:
        frappe.msgprint(_("Feed Provider name is empty!"))
        return
    url = utils.find(args, "url")

    doc = frappe.get_doc("Feed Provider", name)

    if not url:
        url = doc.get("url")

    doc.update({"fetched": frappe.utils.now()}).save()
    frappe.db.commit()

    response = requests.get(url)
    if response.status_code == 200:
        rss = parse(response.content.decode('utf-8'))
        for item in rss:
            frappe.get_doc({
                "doctype": "Feed",
                "provider": name,
                "id": item.get('id'),
                "title": item.get('title'),
                "description": item.get('content') or item.get('description'),
                "url": item.get("link")
            }).insert()
            frappe.db.commit()
        return rss if rss is not None else None


def parse(xml):
    ET.register_namespace("", "http://www.w3.org/2005/Atom")
    root = ET.fromstring(xml)
    entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')

    results = []
    for entry in entries:
        entry_data = {}
        for child in entry:
            tag = child.tag.replace("{http://www.w3.org/2005/Atom}", "")
            if tag == "link":
                link = child.get("href")  # Retrieve the 'href' attribute value
                parsed_url = urlparse(link)
                query_params = parse_qs(parsed_url.query)
                url_param = query_params.get('url', [''])[0]
                entry_data[tag] = url_param
            else:
                entry_data[tag] = decode(child.text)
        results.append(entry_data)

    return results


def decode(text):
    # Unescape
    text = html.unescape(text)
    # Remove HTML tags using a regular expression
    tag_pattern = re.compile(r'<[^>]+>')
    return tag_pattern.sub('', text)
