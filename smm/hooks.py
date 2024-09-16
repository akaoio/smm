app_name = "smm"
app_title = "SMM"
app_publisher = "mimiza"
app_description = "Social Media Marketing and Management system"
app_email = "dev@mimiza.com"
app_license = "MIT"
app_logo_url = "/assets/smm/images/smm-logo.svg"
app_home = "/app/smm"

add_to_apps_screen = [
	{
		"name": "smm",
		"logo": "/assets/smm/images/smm-logo.svg",
		"title": "SMM",
		"route": "/app/smm"
	}
]

scheduler_events = {
    "all": [
        "smm.tasks.x.refresh_access_tokens",
        "smm.tasks.feed.fetch_all",
        "smm.tasks.activity.process_plans",
        "smm.tasks.activity.process_activities",
        "smm.tasks.activity.cast_activities"
    ]
}
