"""
weekly_digest.py
----------------
Called by n8n every Monday at 08:00.
Pulls the top cost anomalies and Compute Optimizer recommendations,
sends them to Claude, and returns a ranked action list.
"""

import os
import json
import boto3
import urllib.request
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ce        = boto3.client("ce")
optimizer = boto3.client("compute-optimizer")


def run_digest() -> dict:
    anomalies       = get_top_anomalies()
    recommendations = get_rightsizing_recommendations()
    ranked_actions  = call_claude(anomalies, recommendations)

    return {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "anomalies":       anomalies,
        "recommendations": recommendations,
        "ranked_actions":  ranked_actions,
    }


def get_top_anomalies(limit: int = 20) -> list:
    """Fetch the top anomalies from Cost Explorer for the past week."""
    end   = datetime.now(timezone.utc).date()
    start = end - timedelta(days=7)

    resp = ce.get_anomalies(
        DateInterval={
            "StartDate": start.isoformat(),
            "EndDate":   end.isoformat(),
        },
        TotalImpact={"NumericOperator": "GREATER_THAN", "StartValue": 10},
        MaxResults=limit,
    )
    results = []
    for a in resp.get("Anomalies", []):
        results.append({
            "service":        a.get("DimensionValue", "unknown"),
            "actual_spend":   round(a["Impact"].get("TotalActualSpend", 0), 2),
            "expected_spend": round(a["Impact"].get("TotalExpectedSpend", 0), 2),
            "impact_pct":     round(a["Impact"].get("TotalImpactPercentage", 0), 1),
            "started":        a.get("AnomalyStartDate", ""),
        })
    return sorted(results, key=lambda x: x["actual_spend"], reverse=True)


def get_rightsizing_recommendations(limit: int = 10) -> list:
    """Fetch over-provisioned EC2 recommendations from Compute Optimizer."""
    resp = optimizer.get_ec2_instance_recommendations(
        filters=[{"name": "Finding", "values": ["OVER_PROVISIONED"]}]
    )
    results = []
    for rec in resp.get("instanceRecommendations", [])[:limit]:
        if not rec.get("recommendationOptions"):
            continue
        best = rec["recommendationOptions"][0]
        tags = {t["key"]: t["value"] for t in rec.get("tags", [])}
        results.append({
            "instance_id":        rec["instanceId"],
            "current_type":       rec["currentInstanceType"],
            "recommended_type":   best["instanceType"],
            "monthly_saving_usd": round(best.get("estimatedMonthlySavings", {}).get("value", 0), 2),
            "cpu_avg_percent":    round(rec.get("utilizationMetrics", [{}])[0].get("value", 0), 1),
            "owner_team":         tags.get("cost:team", "unknown"),
        })
    return sorted(results, key=lambda x: x["monthly_saving_usd"], reverse=True)


def call_claude(anomalies: list, recommendations: list) -> str:
    total_anomaly_impact = sum(
        a["actual_spend"] - a["expected_spend"] for a in anomalies
    )
    total_rightsizing    = sum(r["monthly_saving_usd"] for r in recommendations)

    prompt = f"""You are a FinOps engineer writing a weekly cost digest for an engineering team.
Today is {datetime.now(timezone.utc).strftime('%A %d %B %Y')}.

COST ANOMALIES THIS WEEK (total unexpected spend: ${total_anomaly_impact:.0f}):
{json.dumps(anomalies[:10], indent=2)}

RIGHTSIZING OPPORTUNITIES (total potential saving: ${total_rightsizing:.0f}/month):
{json.dumps(recommendations[:10], indent=2)}

Write a short weekly digest (5-8 sentences max) in plain English.
Then give a numbered list of the top 5 actions ranked by impact.
For each action include: what to do, estimated saving, and risk level.
Be direct. No marketing language."""

    payload = json.dumps({
        "model":      "claude-sonnet-4-20250514",
        "max_tokens": 800,
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


if __name__ == "__main__":
    result = run_digest()
    print(json.dumps(result, indent=2))
