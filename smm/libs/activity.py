import frappe
from frappe import _
from . import utils, x, telegram, openai
import datetime
import copy

fields_map = {
    "mechanism": {
        "type": "array",
        "parent_field": "mechanisms",
        "field_name": "mechanism",
        "child_doctype": "Content Mechanism",
        "filters": {
            "name": {"var": ["linked_item","content_mechanism"]}
        }
    },
    "activity": {
        "type": "array",
        "parent_field": "activities",
        "field_name": "activity",
        "child_doctype": "Network Activity",
        "filters": {
            "name": {"var": ["linked_item", "activity"]}
        }
    },
    "plan": {
        "type": "array",
        "parent_field": "plans",
        "field_name": "activity",
        "child_doctype": "Network Activity",
        "filters": {
            "plan": {"var": ["linked_item", "plan"]},
            "agent": ["!=", {"var": ["agent", "name"]}],
            "status": "Success"
        }
    }
}

requirements_map = {
    "Post Content": ["mechanism"],
    "Post Comment": ["plan", "activity", "mechanism"]
}


class ActivityPlan:
    def __init__(self, **args):
        self.name = utils.find(args, "name")
        self.doc = frappe.get_doc("Network Activity Plan", self.name)
        
        if self.doc.enabled == 0:
            frappe.msgprint(_(f"Network Activity Plan {self.name} is disabled."))
            return

        # Get current date and time using Frappe Utils then convert it to timedelta
        self.current_datetime = datetime.datetime.strptime(frappe.utils.now(), "%Y-%m-%d %H:%M:%S.%f")
        self.current_date = self.current_datetime.date()

        # Get plan's start date and end date
        self.start_date = self.doc.start_date
        self.end_date = self.doc.end_date

        # The base date to calculate the schedule from, defaults to current date
        self.base_date = max(self.start_date if self.start_date else self.current_date, self.current_date)

        # Get current time in timedelta type
        self.current_time = datetime.timedelta(hours=self.current_datetime.hour, minutes=self.current_datetime.minute, seconds=self.current_datetime.second)

        # Get plan's daily time range to generate activity in, defaults to 00:00:00 - 23:59:59
        self.start_time = self.doc.start_time if self.doc.start_time else datetime.timedelta()
        self.end_time = self.doc.end_time if self.doc.end_time else datetime.timedelta(hours=23, minutes=59, seconds=59)

        # duration is in seconds and type is float, convert it to timedelta
        self.duration = datetime.timedelta(seconds=self.doc.duration) if self.doc.duration else datetime.timedelta()

        # Get agents
        self.agents = set()

        # Get agents
        self.agents.update(frappe.get_doc("Agent", item.agent) for item in self.doc.agents)

        # Get agents from agent groups
        for item in self.doc.agent_groups:
            agent_group = frappe.get_doc("Agent Group", item.agent_group).agents
            self.agents.update(frappe.get_doc("Agent", agent.agent) for agent in agent_group)

    

    def schedule(self):
        if self.doc.enabled == 0:
            frappe.msgprint(_(f"Network Activity Plan {self.name} is disabled."))
            return
        
        # Generate one Network Activity for each Agent and for each item of each other required field
        for agent in self.agents:
            # Switch through value of Activity Type
            activity_type = self.doc.activity_type
            required_fields = requirements_map.get(activity_type)
            
            # fields must be dictionary to be able to store unique data
            fields = {}
            if required_fields is not None and len(required_fields) > 0:
                for item in required_fields:
                    field_map = fields_map.get(item)
                    if field_map is not None:
                        # Check if item already exists in fields
                        key = field_map.get("field_name") if field_map.get("field_name") is not None else item
                        fields[key] = fields.get(key) or {"map": field_map, "data": {}}

                        # If field type is array, get the linked items
                        if field_map.get("type") == "array" and field_map.get("child_doctype"):
                            # Linked Item is an Item of the parent Table field which is linked to a child Doctype
                            for linked_item in self.doc.get(field_map.get("parent_field")):
                                # Create a full copy of the original filters map and generate filters from it
                                filters = {}
                                
                                if field_map.get("filters") is not None:
                                    filters = utils.generate_filters(
                                        copy.deepcopy(field_map.get("filters")),
                                        {
                                            "agent": agent,
                                            "linked_item": linked_item
                                        }
                                    )
                                
                                children = frappe.db.get_list(field_map.get("child_doctype"), filters=filters)
                                
                                for child in children:
                                    linked_item_doc = frappe.get_doc(field_map.get("child_doctype"), child.name)
                                    # If `enabled` field doesn't exist or is 1, append the linked item to the array
                                    if linked_item_doc.enabled is None or linked_item_doc.enabled == 1:
                                        fields[key].get("data")[child.name] = linked_item_doc

                        # If field type is single, it is unique by default, so just get the value
                        else: fields[key].get("data")[item] = self.doc.get(item)
            
            # convert fields into array to access it with number
            fields = list(fields.values())

            # This function is used to loop through each item of each array
            def loop(arrays, callback, context={}):
                if len(arrays) == 0:
                    return
                field_map = arrays[0].get("map")
                data = arrays[0].get("data")
                if len(arrays) == 1:
                    for item in data.values():
                        context[field_map.get("field_name")] = item
                        callback(item, context)
                    return
                for item in data.values():
                    # The first argument of callback is the item of the first array
                    # The remaining arguments are the items of the remaining arrays
                    # The remaining arrays are passed to the callback function recursively
                    context[field_map.get("field_name")] = item
                    loop(arrays[1:], callback, context)

            # This function is used to create a Network Activity and is called by loop
            def callback(item, context={}):
                if item.enabled == 0:
                    return

                # Generate filters from context
                filters = {}
                for key, value in context.items():
                    filters[key] = value.name if isinstance(value, frappe.model.document.Document) else value

                base_date = self.base_date
                # If `activity` field exists, get the latest Network Activity scheduled datetime and set it as the base date if possible.
                linked_activity_schedule = self.current_datetime
                if context.get("activity"):
                    linked_activity_schedule = context.get("activity").schedule
                    base_date = max(base_date, linked_activity_schedule.date())

                # The chosen date and timeframe is the nearest one that is possible to create new Network Activity into
                # Loop through each date, started from the date of the current date or Plan start date depending on which one is bigger
                day = 0
                while True:
                    # Date to look upon
                    date = base_date + datetime.timedelta(days=day)

                    # Break if the Network Activity Plan has end date and is expired
                    if self.end_date and date > self.end_date:
                        break

                    # Set schedule datetime to the nearest possible schedule
                    schedule_datetime = utils.comebine_datetime(date, max(self.current_time if date == self.current_date else self.start_time, self.start_time))
                    schedule_datetime = max(schedule_datetime, linked_activity_schedule)

                    # Get the latest Network Activity scheduled datetime within the daily timeframe, based on Agent, Network Activity Plan
                    latest_activity = frappe.db.get_list(
                        "Network Activity",
                        filters={
                            "plan": self.name,
                            "agent": agent.name,
                            "schedule": ["<=", utils.comebine_datetime(date, self.end_time)],
                            **filters
                        },
                        fields=["name", "schedule", "status"],
                        order_by="schedule desc",
                        limit_page_length=1
                    )

                    # The latest Network Activity schedule is then combined with duration to get the next possible schedule
                    # The next possible schedule is then compared with the current datetime to get the nearest possible schedule
                    if len(latest_activity) > 0:
                        latest_activity_datetime = latest_activity[0].schedule
                        if latest_activity_datetime:
                            schedule_datetime = max(latest_activity_datetime + self.duration, schedule_datetime)

                    schedule_date = schedule_datetime.date()
                    schedule_time = datetime.timedelta(hours=schedule_datetime.hour, minutes=schedule_datetime.minute, seconds=schedule_datetime.second)

                    if self.end_date and schedule_date > self.end_date:
                        break

                    if schedule_date > date:
                        day += (schedule_date - date).days
                        continue

                    if self.end_time and schedule_time > self.end_time:
                        day += 1
                        continue

                    # Generate activity
                    frappe.get_doc({
                        "doctype": "Network Activity",
                        "enabled": True,
                        "plan": self.name,
                        "agent": agent.name,
                        "schedule": schedule_datetime,
                        "status": "Pending",
                        **filters
                    }).insert()
                    frappe.db.commit()
                    break

            loop(
                fields,
                callback
            )


@frappe.whitelist()
def generate_activity(**args):
    activity_plan = ActivityPlan(**args)
    activity_plan.schedule()


@frappe.whitelist()
def generate_content(**args):
    name = utils.find(args, "name")
    if not name:
        return
    doc = frappe.get_doc("Network Activity", name)
    # Only generate content for Network Activity with status Pending and without content
    if doc.status != "Pending" or doc.content:
        return
    mechanism = frappe.get_doc("Content Mechanism", doc.mechanism)
    if mechanism.enabled == 0:
        return

    # Generate filters for Content Generator
    required_fields = requirements_map.get(doc.type)
    filters = {}
    for field in required_fields:
        filters[field] = doc.get(field)

    content = openai.generate_content(**filters)
    if content and content.name:
        doc.update({"content": content.name}).save()
        frappe.db.commit()
        return doc


@ frappe.whitelist()
def cast(**args):
    name = utils.find(args, "name")
    if not name:
        return

    doc = frappe.get_doc("Network Activity", name)
    if doc.status != "Pending":
        return

    agent = frappe.get_doc("Agent", utils.find(args, "agent") or doc.agent)
    provider = agent.provider

    linked_external_id = None
    if doc.activity:
        linked_activity = frappe.get_doc("Network Activity", doc.activity)
        if linked_activity.external_id:
            linked_external_id = linked_activity.external_id

    content = utils.find(args, "content")
    content = frappe.get_doc("Content", content) if content else None
    if not content:
        return

    text = utils.remove_quotes(content.description)

    clients = {
        "Telegram": telegram,
        "X": x
    }
    client = clients.get(provider)

    params = {
        "name": name,
        "agent": agent,
        "text": text,
    }

    if linked_external_id:
        params.update({"linked_external_id": linked_external_id})

    response = client.send(**params)

    # If type of response is dict and has json property
    data = response.json()

    # Always get nerd statistics.
    doc.update({
        "payload": {"text": text},
        "response": data,
        "response_status": response.status_code,
    })

    if response.status_code in [200, 201]:
        # The request is successful, now try to get the external id
        doc.update({"status": "Success"})
        if provider == "X":
            external_id = data.get("data").get("id")
        elif provider == "Telegram":
            external_id = data.get("result").get("message_id")
        if external_id:
            doc.update({"external_id": external_id})
    else:
        doc.update({"status": "Failed"})

    doc.save()
    frappe.db.commit()

    return response