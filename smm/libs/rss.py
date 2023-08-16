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
        url = doc.url

    doc.update({"fetched": frappe.utils.now()}).save()
    frappe.db.commit()
    headers = {"Cache-Control": "no-cache"}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        frappe.msgprint(_("Error fetching feed from {0}").format(url))
        return
    elif response.status_code == 200:
        rss = parse(response.content.decode('utf-8'))
        if not rss:
            frappe.msgprint(_("No records found!"))
            return
        for item in rss:
            # Check if the feed already exists before inserting
            feed = frappe.db.get_value("Feed", {"url": item.get("link")})
            if not feed:
                frappe.get_doc({
                    "doctype": "Feed",
                    "provider": name,
                    "title": item.get("title"),
                    "description": item.get("content") or item.get("description"),
                    "url": item.get("link")
                }).insert()
                frappe.db.commit()
        return rss if rss is not None else None


@frappe.whitelist()
def parse(xml=""):
    # Trim xml string, remove spaces and new lines
    xml = xml.strip()

    ET.register_namespace("", "http://www.w3.org/2005/Atom")

    # Validate XML
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        frappe.msgprint(_("Invalid XML!"))
        return

    results = []

    tag = root.tag.replace("{http://www.w3.org/2005/Atom}", "")

    # Check if root is Atom or RSS
    records = root.findall("{http://www.w3.org/2005/Atom}entry") if tag == "feed" else root.find("channel").findall("item") if tag == "rss" else None

    for record in records:
        record_data = {}
        if len(record) > 0:
            for child in record:
                tag = child.tag.replace("{http://www.w3.org/2005/Atom}", "")
                # Make sure to collect only required data
                if tag not in ["title", "content", "description", "link"]:
                    continue
                if tag == "link":
                    link = child.get("href") or child.text or ""  # Retrieve the 'href' attribute value
                    # Check if the link starts with `https://www.google.com/url`, this means that the link is a Google redirect link
                    if link.startswith("https://www.google.com/url"):
                        parsed_url = urlparse(link)
                        query_params = parse_qs(parsed_url.query)
                        link = query_params.get('url', [''])[0]
                    record_data[tag] = link
                else:
                    record_data[tag] = decode(child.text)
            results.append(record_data)

    return results


def decode(text):
    # Unescape
    text = html.unescape(text)
    # Remove HTML tags using a regular expression
    tag_pattern = re.compile(r'<[^>]+>')
    return tag_pattern.sub('', text)
