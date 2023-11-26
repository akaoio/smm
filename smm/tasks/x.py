import frappe
from ..libs import x as client, utils


@frappe.whitelist()
def refresh_access_tokens():
    agents = frappe.db.get_list("Agent", filters={"provider": "X"}, fields=["name", "modified"], order_by="modified asc")
    for agent in agents:
        duration = utils.duration(agent.modified)
        if (duration >= 0):
            client.refresh_access_token(name=agent.name)
    return agents