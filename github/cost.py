#!/usr/bin/env python3
"""
GitHub Actions cost reporter for an organization.
Uses the org-level billing usage API (GitHub enhanced billing platform).
Makes exactly 2 API calls — one for last month, one for MTD.

Usage:
    export GITHUB_TOKEN=ghp_your_token_here
    python3 cost.py

Required token scopes: read:org
"""

import os
import sys
import time
from datetime import date, timedelta

import requests

ORG = "org_name"
BASE_URL = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("Error: GITHUB_TOKEN environment variable is required.\n"
                 "Create one at https://github.com/settings/tokens with scope: read:org")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(url: str, params: dict | None = None) -> dict:
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    if resp.status_code == 429:
        reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait = max(reset - time.time(), 5)
        print(f"Rate limited — waiting {wait:.0f}s...")
        time.sleep(wait)
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_billing_usage(year: int, month: int) -> dict:
    """GET /orgs/{org}/settings/billing/usage — GitHub enhanced billing platform API."""
    return _get(
        f"{BASE_URL}/orgs/{ORG}/settings/billing/usage",
        {"year": year, "month": month},
    )


def summarize_actions(usage: dict) -> float:
    total = 0.0
    for item in usage.get("usageItems", []):
        if item.get("product", "").lower() != "actions":
            continue
        total += item.get("netAmount", item.get("grossAmount", 0))
    return total


def post_to_slack(lm_label: str, lm_total: float, mtd_label: str, mtd_total: float):
    slack_token = os.environ["SLACK_TOKEN"]
    slack_channel = os.environ["SLACK_CHANNEL"]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "GitHub Actions Cost Summary"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Month-to-date* ({mtd_label})"},
                {"type": "mrkdwn", "text": f"*${mtd_total:,.2f}*"},
                {"type": "mrkdwn", "text": f"*Previous month* ({lm_label})"},
                {"type": "mrkdwn", "text": f"*${lm_total:,.2f}*"},
            ],
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "<@U05QERHHFR7>"}],
        },
    ]

    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {slack_token}"},
        json={
            "channel": slack_channel,
            "text": f"GitHub Actions Cost Summary — {mtd_label}: ${mtd_total:,.2f} | {lm_label}: ${lm_total:,.2f}",
            "blocks": blocks,
            "username": "Github_Action_Billing",
        },
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Slack error: {result.get('error')}")


def main():
    today = date.today()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    lm_label = last_month_start.strftime("%B %Y")
    mtd_label = f"{today.strftime('%B %Y')} through {today}"

    lm_usage = get_billing_usage(last_month_start.year, last_month_start.month)
    lm_total = summarize_actions(lm_usage)

    mtd_usage = get_billing_usage(today.year, today.month)
    mtd_total = summarize_actions(mtd_usage)

    print(f"Last Month ({lm_label}): ${lm_total:,.2f}")
    print(f"Month-to-Date ({mtd_label}): ${mtd_total:,.2f}")

    post_to_slack(lm_label, lm_total, mtd_label, mtd_total)
    print("Posted to Slack.")


if __name__ == "__main__":
    main()
