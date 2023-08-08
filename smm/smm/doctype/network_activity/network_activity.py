# Copyright (c) 2023, MIMIZA and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class NetworkActivity(Document):
    def validate(self):
        self.update_title()

    def update_title(self):
        agent = frappe.get_doc("Agent", self.agent)
        plan = frappe.get_doc("Network Activity Plan", self.plan)
        mechanism = frappe.get_doc("Content Mechanism", self.mechanism)
        title = agent.title or ""
        title += f" [{plan.title}]" if plan.title else ""
        title += f" [{self.type}]" if self.type else ""
        title += f" {mechanism.title}" if mechanism.title else ""
        self.title = title
