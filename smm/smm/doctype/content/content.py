# Copyright (c) 2023, MIMIZA and contributors
# For license information, please see license.txt

# import frappe
from ....libs import utils
from frappe.model.document import Document


class Content(Document):
    def validate(self):
        self.update_title()

    def update_title(self):
        title = self.title or self.description
        title = utils.shorten_string(title)
        self.title = title
