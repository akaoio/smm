import re
import time

import frappe
from frappe import _
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from . import utils


@frappe.whitelist()
def fetch(**args):
    url = utils.find(args, "url")
    img_w = utils.find(args, "img_w", 1024)
    img_h = utils.find(args, "img_h", 768)
    if not url:
        frappe.msgprint(_("{0} URL is empty").format(_("Feed Provider")))
        return
    feeds = []
    try:
        image = take_screenshot(url, img_w, img_h)
        feeds.append(
            {
                "title": "Screenshot: " + url + " " + frappe.utils.random_string(18),
                "image": image,
            }
        )
    except Exception:
        frappe.msgprint(_("Error fetching feeds from {0}").format(url))
        return

    # Must return in this format
    return {"payload": {"url": url}, "response": None, "feeds": feeds}


def take_screenshot(url, img_w, img_h):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # chrome_options.add_argument('--force-dark-mode')
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument(f"--window-size={img_w},{img_h}")
    prefs = {"profile.content_settings.exceptions.clipboard": {"*": {"setting": 1}}}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    # Navigate to the URL
    driver.get(url)

    # Wait for a few seconds for the new page to load
    time.sleep(3)
    ss_b64 = driver.get_screenshot_as_base64()

    quit_browser(driver)

    return ss_b64


def quit_browser(driver):
    driver.quit()
