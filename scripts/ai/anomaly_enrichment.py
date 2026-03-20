"""
anomaly_enrichment.py
---------------------
Called by n8n when AWS Cost Anomaly Detection fires an alert.
Fetches context from CloudWatch, GitHub, and resource tags,
sends everything to the Claude API, and returns a structured
explanation with a recommended action.

Can also be run standalone for testing:
    python anomaly_enrichment.py
"""

import os
import json
import boto3
import urllib.request
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ENVIRONMENT       = os.environ.get("ENVIRONMENT", "staging")


def enrich_anomaly(anomaly: dict) -> dict:
    """
    Main entry point. Takes an anomaly dict from the SNS alert,
    fetches supporting context, and returns an AI-enriched finding.

    anomaly = {
        "service":         "Amazon EC2",
        "team":            "payments",
        "environment":     "staging",
        "expected_spend":  420.0,
        "actual_spend":    578.0,
        "resource_id":     "i-0a3f82b1c9d4e5f67",  # optional
        "period_start":    "2025-03-10",
        "period_end":      "2025-03-17",
    }
    """
    resource_id = anomaly.get("resource_id")
    metrics     = get_cloudwatch_metrics(resource_id) if resource_id else {}
    deployments = get_recent_deployments(anomaly.get("team", ""))
    tags        = get_resource_tags(resource_id) if resource_id else {}

    prompt = build_prompt(anomaly, metrics, deployments, tags)
    result = call_claude(prompt)

    return {
        "anomaly":       anomaly,
        "context": {
            "metrics":     metrics,
            "deployments": deployments,
            "tags":        tags,
        },
        "ai_finding": result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_cloudwatch_metrics(instance_id: str) -> dict:
    """Fetch average CPU and network metrics for the past 30 days."""
    cw    = boto3.client("cloudwatch")
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=30)

    def get_metric(metric_name, stat="Average"):
        resp = cw.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName=metric_name,
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start,
            EndTime=end,
            Period=86400,
            Statistics=[stat],
        )
        points = resp.get("Datapoints", [])
        if not points:
            return None
        return round(sum(p[stat] for p in points) / len(points), 2)

    return {
        "cpu_avg_percent":    get_metric("CPUUtilization"),
        "network_out_bytes":  get_metric("NetworkOut", "Sum"),
        "period_days":        30,
    }


def get_recent_deployments(team: str) -> list:
    """
    In production this calls the GitHub API.
    Here we return a structure showing what the data looks like.
    Replace with a real GitHub API call using the token from SSM.
    """
    # Real implementation:
    # token = boto3.client("ssm").get_parameter(
    #     Name="/cost-optimization/github-token", WithDecryption=True
    # )["Parameter"]["Value"]
    # ... call GitHub API ...

    return [
        {
            "repo":        f"{team}-api",
            "ref":         "v2.4.1",
            "deployed_at": (datetime.now(timezone.utc) - timedelta(hours=19)).isoformat(),
            "author":      "engineer@example.com",
        }
    ]


def get_resource_tags(resource_id: str) -> dict:
    """Fetch tags for an EC2 instance."""
    ec2  = boto3.client("ec2")
    resp = ec2.describe_tags(
        Filters=[{"Name": "resource-id", "Values": [resource_id]}]
    )
    return {t["Key"]: t["Value"] for t in resp.get("Tags", [])}


def build_prompt(anomaly, metrics, deployments, tags) -> str:
    pct_over = round(
        (anomaly["actual_spend"] - anomaly["expected_spend"])
        / anomaly["expected_spend"] * 100, 1
    )
    return f"""You are a FinOps engineer reviewing a cloud cost anomaly.
Respond in JSON only. No preamble or explanation outside the JSON.

ANOMALY:
  Service:          {anomaly["service"]}
  Team:             {anomaly["team"]}
  Environment:      {anomaly["environment"]}
  Expected spend:   ${anomaly["expected_spend"]}/week
  Actual spend:     ${anomaly["actual_spend"]}/week  (+{pct_over}%)
  Period:           {anomaly.get("period_start")} to {anomaly.get("period_end")}

INSTANCE METRICS (30-day average):
  CPU utilisation:  {metrics.get("cpu_avg_percent", "N/A")}%
  Network out:      {metrics.get("network_out_bytes", "N/A")} bytes/day avg

RECENT DEPLOYMENTS:
{json.dumps(deployments, indent=2)}

RESOURCE TAGS:
{json.dumps(tags, indent=2)}

Respond with this exact JSON structure:
{{
  "finding": "one sentence describing what is happening",
  "root_cause": "2-3 sentences explaining why",
  "recommended_action": "specific steps to fix it",
  "estimated_monthly_saving_usd": <number>,
  "risk_level": "LOW | MEDIUM | HIGH",
  "validation_step": "how to verify before applying to production",
  "confidence_pct": <0-100>
}}"""


def call_claude(prompt: str) -> dict:
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
        text = body["content"][0]["text"]
        # Strip any accidental markdown fences
        text = text.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(text)


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_anomaly = {
        "service":        "Amazon EC2",
        "team":           "payments",
        "environment":    "staging",
        "expected_spend": 420.0,
        "actual_spend":   578.0,
        "resource_id":    "i-0a3f82b1c9d4e5f67",
        "period_start":   "2025-03-10",
        "period_end":     "2025-03-17",
    }
    result = enrich_anomaly(test_anomaly)
    print(json.dumps(result, indent=2))
