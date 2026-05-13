#!/usr/bin/env python3

import os
import requests
from datetime import datetime, timezone, timedelta

API_KEY = os.environ["DD_API_KEY"]
APP_KEY = os.environ["DD_APP_KEY"]

now = datetime.now(timezone.utc)
today = now.date()

# Datadog billing data has a 2-day lag
end_date = today - timedelta(days=0)
start_date = today.replace(day=1)

url = "https://api.datadoghq.com/api/v2/usage/estimated_cost"

headers = {
    "DD-API-KEY": API_KEY,
    "DD-APPLICATION-KEY": APP_KEY,
    "Content-Type": "application/json",
}

params = {
    "start_date": start_date.strftime("%Y-%m-%d"),
    "end_date": end_date.strftime("%Y-%m-%d"),
    "cost_aggregation": "cumulative",
}

response = requests.get(url, headers=headers, params=params)
response.raise_for_status()

data = response.json()

# With cumulative aggregation, the last entry holds the month-to-date total
last_entry = data.get("data", [{}])[-1]
total_cost = last_entry.get("attributes", {}).get("total_cost", 0.0)

mtd_cost = round(total_cost, 2)
print(f"{start_date} to {end_date}: ${mtd_cost}")

# monthly cost
prev_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
curr_month = now.strftime("%Y-%m")
params = {
    "start_month": prev_month,
    "end_month": curr_month,
}

response = requests.get(url, headers=headers, params=params)
response.raise_for_status()

data = response.json()

total_cost = 0.0

for item in data.get("data", []):
    attributes = item.get("attributes", {})
    total_cost += attributes.get("total_cost", 0.0)

prev_month_cost = round(total_cost, 2)
print(f"{prev_month}: ${prev_month_cost}")

# post the result to slack channel
SLACK_TOKEN = os.environ["SLACK_TOKEN"]
SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]

blocks = [
    {
        "type": "header",
        "text": {"type": "plain_text", "text": "Datadog Cost Summary"},
    },
    {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*Month-to-date* ({start_date} to {end_date})"},
            {"type": "mrkdwn", "text": f"*${mtd_cost:,.2f}*"},
            {"type": "mrkdwn", "text": f"*Previous month* ({prev_month})"},
            {"type": "mrkdwn", "text": f"*${prev_month_cost:,.2f}*"},
        ],
    },
    {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "<@U05QERHHFR7>"}],
    },
]

slack_response = requests.post(
    "https://slack.com/api/chat.postMessage",
    headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
    json={
        "channel": SLACK_CHANNEL,
        "text": f"Datadog Cost Summary — {start_date} to {end_date}: ${mtd_cost:,.2f} | {prev_month}: ${prev_month_cost:,.2f}",
        "blocks": blocks,
        "username": "Datadog_Billing",
        "icon_emoji": ":dd_logo_v_white:"
    },
)
slack_response.raise_for_status()
result = slack_response.json()
if not result.get("ok"):
    raise RuntimeError(f"Slack error: {result.get('error')}")
