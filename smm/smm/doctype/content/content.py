# Copyright (c) 2023, MIMIZA and contributors
# For license information, please see license.txt

import frappe
from ....libs import utils
from frappe.model.document import Document


class Content(Document):
    def validate(self):
        self.update_title()

    def update_title(self):
        title = self.title or self.description
        if self.mechanism:
            mechanism = frappe.get_doc("Content Mechanism", self.mechanism)
            title = mechanism.get("title") + " " + frappe.utils.random_string(24)
        title = utils.shorten_string(title)
        self.title = title