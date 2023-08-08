app_name = "smm"
app_title = "SMM"
app_publisher = "mimiza"
app_description = "Social Media Marketing and Management system"
app_email = "dev@mimiza.com"
app_license = "MIT"

scheduler_events = {
    "all": [
        "smm.tasks.twitter.refresh_tokens",
        "smm.tasks.rss.fetch_all",
        "smm.tasks.activity.process_activities",
        "smm.tasks.activity.cast_activities"
    ]
}
