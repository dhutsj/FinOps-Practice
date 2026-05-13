import boto3
import os
import requests
from datetime import date
from dateutil.relativedelta import relativedelta

ACCOUNTS = {
    "dev_account": {
        "aws_access_key_id": os.environ["DEV_ACCOUNT_ACCESS_KEY"],
        "aws_secret_access_key": os.environ["DEV_ACCOUNT_SECRET_KEY"],
    },
    "staging_account": {
        "aws_access_key_id": os.environ["STAGING_ACCOUNT_ACCESS_KEY"],
        "aws_secret_access_key": os.environ["STAGING_ACCOUNT_SECRET_KEY"],
    },
    "prod_account": {
        "aws_access_key_id": os.environ["PROD_ACCOUNT_ACCESS_KEY"],
        "aws_secret_access_key": os.environ["PROD_ACCOUNT_SECRET_KEY"],
    },
}


def get_cost(client, start: str, end: str) -> float:
    response = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    total = sum(
        float(result["Total"]["UnblendedCost"]["Amount"])
        for result in response["ResultsByTime"]
    )
    return total


def main():
    today = date.today()
    # Last month
    first_of_this_month = today.replace(day=1)
    first_of_last_month = first_of_this_month - relativedelta(months=1)
    last_month_start = first_of_last_month.isoformat()
    last_month_end = first_of_this_month.isoformat()
    # Month-to-date
    mtd_start = first_of_this_month.isoformat()
    mtd_end = today.isoformat()

    print(f"Last month : {last_month_start} → {last_month_end}")
    print(f"MTD        : {mtd_start} → {mtd_end}")
    print()

    totals = {"last_month": 0.0, "mtd": 0.0}
    results = {}

    for name, creds in ACCOUNTS.items():
        client = boto3.client("ce", region_name="us-east-1", **creds)
        last_month_cost = get_cost(client, last_month_start, last_month_end)
        mtd_cost = get_cost(client, mtd_start, mtd_end) if mtd_start != mtd_end else 0.0
        totals["last_month"] += last_month_cost
        totals["mtd"] += mtd_cost
        results[name] = {"last_month": last_month_cost, "mtd": mtd_cost}
        print(f"{name}:")
        print(f"  Last month : ${last_month_cost:>10.2f}")
        print(f"  MTD        : ${mtd_cost:>10.2f}")

    print()
    print("─" * 30)
    print(f"TOTAL last month : ${totals['last_month']:>10.2f}")
    print(f"TOTAL MTD        : ${totals['mtd']:>10.2f}")

    SLACK_TOKEN = os.environ["SLACK_TOKEN"]
    SLACK_CHANNEL = os.environ["SLACK_CHANNEL"]

    account_fields = []
    for name, costs in results.items():
        account_fields += [
            {"type": "mrkdwn", "text": f"*{name}*"},
            {"type": "mrkdwn", "text": f"Last month: *${costs['last_month']:,.2f}* | MTD: *${costs['mtd']:,.2f}*"},
        ]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "AWS Cost Summary"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total — Last month* ({last_month_start} → {last_month_end})"},
                {"type": "mrkdwn", "text": f"*${totals['last_month']:,.2f}*"},
                {"type": "mrkdwn", "text": f"*Total — MTD* ({mtd_start} → {mtd_end})"},
                {"type": "mrkdwn", "text": f"*${totals['mtd']:,.2f}*"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": account_fields,
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
            "text": f"AWS Cost Summary — Last month: ${totals['last_month']:,.2f} | MTD: ${totals['mtd']:,.2f}",
            "blocks": blocks,
            "username": "AWS_Billing",
            "icon_emoji": ":aws-dark:"
        },
    )
    slack_response.raise_for_status()
    result = slack_response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Slack error: {result.get('error')}")


if __name__ == "__main__":
    main()
