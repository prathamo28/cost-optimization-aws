"""
iac_review.py
-------------
Called by GitHub Actions on every Terraform PR.
Sends the terraform plan output to Claude and returns
cost improvement suggestions posted as a PR comment.

Usage:
    python iac_review.py --plan-file plan.json --pr-number 42
"""

import os
import sys
import json
import argparse
import urllib.request

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO       = os.environ.get("GITHUB_REPO", "your-org/cost-optimization-aws")


def review_plan(plan_json: dict) -> str:
    """Send terraform plan to Claude and get cost review back."""
    # Extract only the resource changes — keep the prompt focused
    changes = [
        {
            "address": r["address"],
            "type":    r["type"],
            "action":  r["change"]["actions"],
            "after":   r["change"].get("after", {}),
        }
        for r in plan_json.get("resource_changes", [])
        if r["change"]["actions"] != ["no-op"]
    ]

    if not changes:
        return "No infrastructure changes detected in this plan."

    prompt = f"""You are a FinOps engineer reviewing a Terraform plan for cost issues.
Review the planned changes below and identify any cost inefficiencies.
Be specific — name the resource and explain exactly what to change and why.
If everything looks fine, say so briefly.

PLANNED CHANGES:
{json.dumps(changes, indent=2)}

Format your response as:
- One sentence overall assessment
- Bullet list of specific findings (if any), each with: resource, issue, suggested fix, estimated impact
- If no issues: confirm the plan looks cost-efficient

Keep it short. Engineers will read this as a PR comment."""

    payload = json.dumps({
        "model":      "claude-sonnet-4-20250514",
        "max_tokens": 600,
        "messages":   [{"role": "user", "content": prompt}]
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


def post_pr_comment(pr_number: int, comment: str):
    """Post the review as a comment on the GitHub PR."""
    body = f"""### AI cost review

{comment}

---
*This comment was generated automatically. It is advisory — review before acting.*"""

    payload = json.dumps({"body": body}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues/{pr_number}/comments",
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
        },
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print(f"Comment posted: {result['html_url']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-file", required=True, help="Path to terraform plan JSON file")
    parser.add_argument("--pr-number", type=int,      help="GitHub PR number to comment on")
    args = parser.parse_args()

    with open(args.plan_file) as f:
        plan = json.load(f)

    review = review_plan(plan)
    print(review)

    if args.pr_number:
        post_pr_comment(args.pr_number, review)


if __name__ == "__main__":
    main()
