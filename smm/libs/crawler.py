import re
import time

import frappe
from frappe import _
from selenium import webdriver
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from . import utils


@frappe.whitelist()
def fetch(**args):
    url = utils.find(args, "url")
    if not url:
        frappe.msgprint(_("{0} URL is empty").format(_("Feed Provider")))
        return
    feeds = []

    try:
        clipboard_data = capture_tradingview_screenshot(url)
        chart_image_url = convert_tradingview_links(
             str(clipboard_data)
        )
        feeds.append({"title": "Screenshot: "+chart_image_url, "image_url": chart_image_url})
    except Exception:
        frappe.msgprint(_("Error fetching feeds from {0}").format(url))
        return

    # Must return in this format
    return {"payload": {"url": url}, "response": None, "feeds": feeds}


def capture_tradingview_screenshot(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # chrome_options.add_argument('--force-dark-mode')
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1024,768")
    prefs = {"profile.content_settings.exceptions.clipboard": {"*": {"setting": 1}}}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    # Navigate to the URL
    driver.get(url)

    # Wait for a few seconds for the new page to load
    time.sleep(3)

    driver.set_permissions("clipboard-write", "granted")

    ActionChains(driver).key_down(Keys.ALT).key_down("s").key_up(Keys.ALT).key_up(
        "s"
    ).perform()
    driver.set_permissions("clipboard-read", "granted")
    time.sleep(10)
    clipboard = driver.execute_script("return await navigator.clipboard.readText();")
    time.sleep(5)
    quit_browser(driver)

    return clipboard


def quit_browser(driver):
    driver.quit()


def convert_tradingview_links(input_string):
    # Define a regex pattern to find links of the format 'https://www.tradingview.com/x/...'
    pattern = r"https://www\.tradingview\.com/x/([a-zA-Z0-9]+)/"

    # Find all matching links in the input string
    matches = re.findall(pattern, input_string)

    # Iterate through the matches and replace them
    for match in matches:
        old_link = f"https://www.tradingview.com/x/{match}/"
        new_link = (
            f"https://s3.tradingview.com/snapshots/{match[0].lower()}/{match}.png"
        )
        input_string = input_string.replace(old_link, new_link)

    return input_string
