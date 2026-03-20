"""
rightsizing_pr.py
-----------------
Runs every Monday at 07:00 UTC.
Reads Compute Optimizer recommendations, calls the Claude API
for a plain-English summary, and opens a GitHub PR with the
proposed Terraform instance type changes.
"""

import os
import json
import boto3
import urllib.request
import urllib.error
from datetime import datetime, timezone

optimizer  = boto3.client("compute-optimizer")
sns        = boto3.client("sns")

ENVIRONMENT       = os.environ["ENVIRONMENT"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SNS_TOPIC_ARN     = os.environ["SNS_TOPIC_ARN"]
GITHUB_REPO       = os.environ.get("GITHUB_REPO", "your-org/cost-optimization-aws")
GITHUB_BASE_BRANCH = os.environ.get("GITHUB_BASE_BRANCH", "main")


def lambda_handler(event, context):
    recommendations = get_recommendations()

    if not recommendations:
        print("No rightsizing recommendations found this week.")
        return {"status": "no_recommendations"}

    summary = get_ai_summary(recommendations)
    pr_url  = open_github_pr(recommendations, summary)

    notify(recommendations, summary, pr_url)

    return {"status": "pr_opened", "pr_url": pr_url}


def get_recommendations():
    """Fetch EC2 rightsizing recommendations from Compute Optimizer."""
    response = optimizer.get_ec2_instance_recommendations(
        filters=[{"name": "Finding", "values": ["OVER_PROVISIONED"]}]
    )
    results = []
    for rec in response.get("instanceRecommendations", []):
        if not rec.get("recommendationOptions"):
            continue
        best = rec["recommendationOptions"][0]
        tags = {t["key"]: t["value"] for t in rec.get("tags", [])}

        if tags.get("cost:env") == "prod" and ENVIRONMENT != "prod":
            continue

        results.append({
            "instance_id":         rec["instanceId"],
            "instance_name":       rec.get("instanceName", ""),
            "current_type":        rec["currentInstanceType"],
            "recommended_type":    best["instanceType"],
            "monthly_saving_usd":  round(best.get("estimatedMonthlySavings", {}).get("value", 0), 2),
            "cpu_avg_percent":     round(rec.get("utilizationMetrics", [{}])[0].get("value", 0), 1),
            "memory_avg_percent":  round(rec.get("utilizationMetrics", [{}])[-1].get("value", 0), 1),
            "owner_team":          tags.get("cost:team", "unknown"),
            "environment":         tags.get("cost:env", ENVIRONMENT),
        })

    # Sort by highest saving first
    return sorted(results, key=lambda x: x["monthly_saving_usd"], reverse=True)


def get_ai_summary(recommendations):
    """Ask Claude to produce a plain-English summary of the recommendations."""
    prompt = f"""You are a FinOps engineer. Here are this week's EC2 rightsizing recommendations.
Write a short summary (3-5 sentences) explaining the findings in plain English for an engineering team.
Then list the top 3 actions ranked by saving. Be direct and specific.

Recommendations (JSON):
{json.dumps(recommendations[:10], indent=2)}

Respond in plain text. No markdown."""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
        return body["content"][0]["text"]


def open_github_pr(recommendations, summary):
    """Create a branch and open a PR with the Terraform changes."""
    date_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    branch_name = f"cost/rightsizing-{date_str}"

    # Build the PR body
    table_rows = "\n".join([
        f"| {r['instance_id']} | {r['current_type']} | {r['recommended_type']} "
        f"| {r['cpu_avg_percent']}% | ${r['monthly_saving_usd']} | {r['owner_team']} |"
        for r in recommendations[:10]
    ])

    pr_body = f"""## Weekly rightsizing recommendations — {date_str}

### AI summary
{summary}

### Recommended changes

| Instance | Current type | Recommended type | CPU avg | Monthly saving | Team |
|----------|-------------|-----------------|---------|----------------|------|
{table_rows}

### How to apply
1. Review each change — confirm with the owning team that no special requirements exist
2. Update the `instance_type` variable in the relevant Terraform environment file
3. Apply to staging first and monitor for 48 hours
4. Apply to production after staging validation passes

> This PR was opened automatically by the rightsizing Lambda.
> All changes require human review before merging.
"""

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
    }

    # Get the SHA of the base branch to create a new branch from
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/git/ref/heads/{GITHUB_BASE_BRANCH}",
        headers=headers
    )
    with urllib.request.urlopen(req) as resp:
        sha = json.loads(resp.read())["object"]["sha"]

    # Create branch
    urllib.request.urlopen(urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/git/refs",
        data=json.dumps({"ref": f"refs/heads/{branch_name}", "sha": sha}).encode(),
        headers=headers,
        method="POST"
    ))

    # Open the PR
    pr_payload = json.dumps({
        "title": f"cost: weekly rightsizing recommendations {date_str}",
        "body":  pr_body,
        "head":  branch_name,
        "base":  GITHUB_BASE_BRANCH,
        "labels": ["cost-optimization", "automated"],
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/pulls",
        data=pr_payload,
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        pr = json.loads(resp.read())
        return pr["html_url"]


def notify(recommendations, summary, pr_url):
    total_saving = sum(r["monthly_saving_usd"] for r in recommendations)
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"[Cost] Weekly rightsizing — {len(recommendations)} recommendations, ${total_saving:.0f}/month potential saving",
        Message=f"{summary}\n\nFull recommendations and Terraform changes: {pr_url}",
    )
