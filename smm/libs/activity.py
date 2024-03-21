import copy
import datetime

import frappe
from frappe import _
from frappe.utils import get_site_name

from . import openai, telegrambot, utils, x

# Based on the type of Network Activity, the required fields are different
requirements = {
    "Post Content": ["mechanism"],
    "Post Comment": ["plan", "activity", "mechanism"],
    "Share Content": ["plan", "activity", "mechanism"]
}

# Field properties
props = {
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
        "query": "plan_query"
    }
}


class ActivityPlan:
    def __init__(self, **args):
        self.name = utils.find(args, "name")
        
        if not frappe.db.exists("Network Activity Plan", self.name):
            frappe.msgprint(_("{0} {1} does not exist").format(_("Network Activity Plan"), self.name))
            return
        
        self.doc = frappe.get_doc("Network Activity Plan", self.name)
        
        self.owner = self.doc.owner or frappe.get_user().name
        
        if self.doc.enabled == 0:
            frappe.msgprint(_("{0} {1} is disabled").format(_("Network Activity Plan"), self.name))
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
        
        # Generate an array of names of agent groups from self.doc.agent_groups
        agent_groups = [item.agent_group for item in self.doc.agent_groups]
        if agent_groups:
            # Use query builder to get the list of agents from the agent groups array
            agent_group_item = frappe.qb.DocType("Agent Group Item")
            query = frappe.qb.from_(agent_group_item).select("parent").distinct().where(
                agent_group_item.agent_group.isin(agent_groups)
                & (agent_group_item.parenttype == "Agent")
                & (agent_group_item.parentfield == "agent_groups")
            )
            agents = query.run(as_dict=True)
            self.agents.update(frappe.get_doc("Agent", item.parent) for item in agents)
    

    # This function is used to loop through each item of each array
    def loop(self, arrays, callback, context={}):
        if len(arrays) == 0:
            return
        field = arrays[0].get("field")
        data = arrays[0].get("data")
        # If there is only one array left, loop through each item of the array and call the callback function
        if len(arrays) == 1:
            # The first argument of callback is the item of the array
            for item in data.values():
                context[field.get("field_name")] = item
                # Execute the callback function with context, which is generator in this case
                callback(item, context)
            return
        # If there are more than one array, loop through each item of each array
        for item in data.values():
            # The first argument of callback is the item of the first array
            # The remaining arguments are the items of the remaining arrays
            # The remaining arrays are passed to the callback function recursively
            context[field.get("field_name")] = item
            self.loop(arrays[1:], callback, context)


    # This function is used to create a Network Activity and is called by self.loop
    def generator(self, item, context={}):
        if item.enabled == 0 or context.get("agent") is None:
            return
        
        agent = context.get("agent")

        # Generate filters from context
        filters = {}
        for key, value in context.items():
            filters[key] = value.name if isinstance(value, frappe.model.document.Document) else value

        # Count the number of Pending Activities of the Agent for these filters upto the current date
        pending_activities = frappe.db.count(
            "Network Activity",
            {
                "plan": self.name,
                "agent": agent.name,
                "status": "Pending",
                "schedule": [">=", self.current_datetime],
                **filters
            }
        )

        # If there is already a Pending Activity, don't create new one
        if pending_activities >= 1:
            return

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
            # The schedule datetime is the maximum value between the current datetime and the start datetime of the Network Activity Plan
            schedule_datetime = utils.comebine_datetime(date, max(self.current_time if date == self.current_date else self.start_time, self.start_time))
            schedule_datetime = max(schedule_datetime, linked_activity_schedule)

            # Get the latest Network Activity scheduled datetime within the daily timeframe, based on Agent, Network Activity Plan
            # WHY DO WE NEED THIS? Because we don't want to duplicate Network Activity within the same timeframe
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

            # Generate Network Activity and break the loop
            frappe.get_doc({
                "owner": self.owner,
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
    
    # Custom query function for `plan` field
    def plan_query(self, context={}):
        doctype = frappe.qb.DocType(context.get("field").get("child_doctype"))
        plan = context.get("linked_item").get("plan")
        agent = context.get("agent").get("name")

        # Get the list of Network Activities created by the agent
        subquery = frappe.qb.from_(doctype).select(doctype.activity).distinct().where(
            (doctype.agent == agent) &
            doctype.type.isin(["Post Comment", "Share Content"]) &
            doctype.status.isin(["Pending", "Success"])
        )
        
        # Get the list of Network Activities created by other agents that are not in the list of Network Activities created by the agent
        query = frappe.qb.from_(doctype).select(doctype.name).distinct().where(
            (doctype.plan == plan) &
            (doctype.agent != agent) &
            (doctype.type == "Post Content") &
            (doctype.status == "Success") &
            doctype.name.notin(subquery)
        ).run(as_dict=True)

        return query
    
    
    def schedule(self):
        if self.doc.enabled == 0:
            frappe.msgprint(_("{0} {1} is disabled").format(_("Network Activity Plan"), self.name))
            return
        
        # Switch through value of Activity Type
        activity_type = self.doc.activity_type
        required_fields = requirements.get(activity_type)
            
        # Generate one Network Activity for each Agent and for each item of each other required field
        for agent in self.agents:
            # fields must be dictionary to be able to store unique data
            fields = {}
            if required_fields is not None and len(required_fields) > 0:
                for item in required_fields:
                    field = props.get(item)
                    if field is not None:
                        # Check if item already exists in fields
                        key = field.get("field_name") if field.get("field_name") is not None else item
                        fields[key] = fields.get(key) if fields.get(key) is not None else {"field": field, "data": {}}

                        # If field type is array, get the linked items
                        if field.get("type") == "array" and field.get("child_doctype"):
                            # Linked Item is an Item of the parent Table field which is linked to a child Doctype
                            for linked_item in self.doc.get(field.get("parent_field")):
                                children = None
                                context = {"field": field, "agent": agent, "linked_item": linked_item}
                                
                                # Check if the field has its own query function
                                # This is used when the query is more complex than just getting the list of linked items
                                # The function must return an array of linked items
                                if field.get("query") is not None and hasattr(self, field.get("query")) and callable(getattr(self, field.get("query"))):
                                    children = getattr(self, field.get("query"))(context)
                                
                                # If the field doesn't have its own query function, generate filters from context and get the list of linked items
                                else:
                                    # Create a full copy of the original filters map and generate filters from it
                                    filters = {}
                                    
                                    if field.get("filters") is not None:
                                        filters = utils.transform(
                                            copy.deepcopy(field.get("filters")),
                                            context
                                        )
                                
                                    # Get the list of linked items using the generated filters
                                    # This part needs improvement to be able to get the list of linked items with deeper filters
                                    children = frappe.db.get_list(field.get("child_doctype"), filters=filters)
                                
                                if children is not None:
                                    for child in children:
                                        linked_item_doc = frappe.get_doc(field.get("child_doctype"), child.name)
                                        # If `enabled` field doesn't exist or is 1, append the linked item to the array
                                        # Make sure the linked item doesn't already exist in the array
                                        if (linked_item_doc.enabled is None or linked_item_doc.enabled == 1) and fields[key].get("data").get(child.name) is None:
                                            fields[key].get("data")[child.name] = linked_item_doc

                        # If field type is single, it is unique by default, so just get the value
                        # Make sure the value doesn't already exist in the array
                        elif fields[key].get("data").get(item) is None: fields[key].get("data")[item] = self.doc.get(item)
            
            # Convert fields into array to access it with number
            fields = list(fields.values())

            # Generate Network Activities
            self.loop(
                fields,
                self.generator,
                {"agent": agent}
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

    # Create filters for Content Generator
    required_fields = requirements.get(doc.type)
    filters = {}
    for field in required_fields:
        filters[field] = doc.get(field)

    content = openai.generate_content(**filters)
    if content and content.get("name"):
        doc.update({"content": content.name}).save()
        frappe.db.commit()
        return doc


@frappe.whitelist()
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

    content = utils.find(args, "content") or doc.content
    content = frappe.get_doc("Content", content) if content else None
    if not content:
        return
    
    text = utils.remove_quotes(content.description)
    
    clients = {
        "Telegram Bot": telegrambot,
        "X": x
    }
    client = clients.get(provider)

    params = {
        "name": name,
        "agent": agent,
        "text": text,
        "type": doc.type,
    }

    if content.get("image") is not None:
        image = frappe.get_value(
            "File", {"file_url": content.image}, "file_name")
        image = frappe.utils.file_manager.get_file(image)
        params.update(
            {
                "image": image[1],
                "image_path": get_site_name(frappe.local.request.host) + content.image,
            }
        )

    if linked_external_id:
        params.update({"linked_external_id": linked_external_id})

    if not hasattr(client, "send") or not callable(getattr(client, "send")):
        return
    response = client.send(**params)
    #TEST TEST TEST
    return

    # If type of response is dict and has json property
    data = response.json()
    del params["agent"]
    # Always get nerd statistics.
    doc.update({
        "payload": params,
        "response": data,
        "response_status": response.status_code,
    })

    if response.status_code in [200, 201]:
        # The request is successful, now try to get the external id
        doc.update({"status": "Success"})
        if provider == "X":
            external_id = data.get("data").get("id")
        elif provider == "Telegram Bot":
            external_id = data.get("result").get("message_id")
        if external_id:
            doc.update({"external_id": external_id})
    else:
        doc.update({"status": "Failed"})

    doc.save()
    frappe.db.commit()

    return response