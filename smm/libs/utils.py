import frappe
import json
from datetime import datetime, timedelta
import re


def doc_data(data):
    return json.loads(data.get("doc") or frappe.form_dict.get("doc")) if data.get("doc") else None


def find(args, key, default=None):
    data = args.get(key)
    return data if data is not None else (data := doc_data(args)) and data.get(key) if doc_data(args) else default


def duration(time, unit="second", format="%Y-%m-%d %H:%M:%S.%f"):
    time = datetime.strptime(time, format) if isinstance(time, str) else time if isinstance(time, datetime) else None
    return None if not isinstance(time, datetime) else int((datetime.now() - time).total_seconds() / 60) if unit == "minute" else int((datetime.now() - time).total_seconds())


def remove_quotes(text):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def remove_mentions(input_string):
    # Define the regular expression pattern to match '@username'
    pattern = r'@(\S+)'  # \S matches any non-whitespace character, + matches one or more occurrences

    # Use re.sub to replace the matched pattern with an empty string
    result = re.sub(pattern, '', input_string)

    # Replace multiple spaces with a single space
    result = re.sub(r'\s+', ' ', result)

    return result.strip()  # Remove leading and trailing spaces (if any)


def comebine_datetime(date, time, end=False):
    # Generate datetime from given `date` and `time`. If `time` doesn't exist, make it 00:00:00. If `time` exists and `end` is True, make it 23:59:59
    if not time:
        time = timedelta(hours=0, minutes=0, seconds=0)
        if end:
            time = timedelta(hours=23, minutes=59, seconds=59)
    return datetime.combine(date, datetime.min.time()) + time if date is not None else None


def loop_nested_arrays(arrays, callback):
    if len(arrays) == 0:
        return
    if len(arrays) == 1:
        for item in arrays[0]:
            callback(item)
        return
    for item in arrays[0]:
        # The first argument of callback is the item of the first array
        # The remaining arguments are the items of the remaining arrays
        # The remaining arrays are passed to the callback function recursively
        loop_nested_arrays(arrays[1:], callback)


def shorten_string(input, length=60):
    if len(input) <= length:
        return input
    else:
        return input[:length - 3] + "..."

def generate_filters(filters={}, context={}):
    # Sample input: {"key": {"var": ["context_key", "context_key2"]}}
    # Filters:
    # {
    #     "plan": {"var": ["linked_item", "plan"]},
    #     "agent": ["!=", {"var": ["agent", "name"]}],
    #     "status": "Success"
    # }
    # Context:
    # {
    #     "self": self,
    #     "linked_item": linked_item,
    #     "agent": agent,
    # }
    
    # For dict
    if isinstance(filters, dict):
        # If the input contains "var", replace it with relevent context value.
        if filters.get("var") is not None:
            searcher = None
            for item in filters.get("var"):
                searcher = context.get(item) if searcher is None else searcher.get(item)
            return searcher
        # For normal dict, just loop.
        for key, props in filters.items():
            filters[key] = generate_filters(props, context)
    
    # For array
    if isinstance(filters, list):
        for index, props in enumerate(filters):
            if isinstance(props, dict) and props.get("var") is not None:
                filters[index] = generate_filters(props, context)
    
    # By default, just return filters.
    return filters