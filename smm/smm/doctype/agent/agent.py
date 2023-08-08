# Copyright (c) 2023, MIMIZA and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Agent(Document):
    def validate(self):
        self.update_title()

    def update_title(self):
        self.title = f"{self.username} [{self.provider}]"
