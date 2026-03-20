"""
forecast_narrative.py
---------------------
Called monthly. Fetches the AWS Cost Explorer forecast for
the next 90 days and asks Claude to translate the numbers
into a plain-English paragraph for the leadership report.
"""

import os
import json
import boto3
import urllib.request
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ce = boto3.client("ce")


def generate_narrative() -> dict:
    forecast = get_forecast()
    last_month_actual = get_last_month_actual()
    narrative = call_claude(forecast, last_month_actual)

    return {
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "forecast":          forecast,
        "last_month_actual": last_month_actual,
        "narrative":         narrative,
    }


def get_forecast() -> dict:
    """Get 90-day spend forecast from Cost Explorer."""
    today    = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=90)

    resp = ce.get_cost_forecast(
        TimePeriod={
            "Start": today.isoformat(),
            "End":   end_date.isoformat(),
        },
        Metric="UNBLENDED_COST",
        Granularity="MONTHLY",
    )
    results = []
    for period in resp.get("ForecastResultsByTime", []):
        results.append({
            "month":           period["TimePeriod"]["Start"][:7],
            "forecast_usd":    round(float(period["MeanValue"]), 2),
            "lower_bound_usd": round(float(period.get("PredictionIntervalLowerBound", 0)), 2),
            "upper_bound_usd": round(float(period.get("PredictionIntervalUpperBound", 0)), 2),
        })
    return results


def get_last_month_actual() -> dict:
    """Get last month's actual spend for comparison."""
    today      = datetime.now(timezone.utc).date()
    first_this = today.replace(day=1)
    last_month_end   = first_this - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    resp = ce.get_cost_and_usage(
        TimePeriod={
            "Start": last_month_start.isoformat(),
            "End":   first_this.isoformat(),
        },
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    total = sum(
        float(r["Total"]["UnblendedCost"]["Amount"])
        for r in resp.get("ResultsByTime", [])
    )
    return {
        "month":      last_month_start.strftime("%Y-%m"),
        "actual_usd": round(total, 2),
    }


def call_claude(forecast: list, last_month: dict) -> str:
    next_month = forecast[0] if forecast else {}
    trend = "increasing" if (
        next_month.get("forecast_usd", 0) > last_month["actual_usd"]
    ) else "decreasing"

    prompt = f"""You are a FinOps engineer writing one paragraph for a monthly leadership report.
Write in plain English. No jargon. No bullet points. Maximum 5 sentences.

LAST MONTH ACTUAL:
  {last_month["month"]}: ${last_month["actual_usd"]:,.0f}

90-DAY FORECAST:
{json.dumps(forecast, indent=2)}

The trend is {trend}.

Write a single paragraph that:
1. States what was spent last month
2. Says what the forecast shows for the next 1-3 months
3. Flags any concern if spend is trending up significantly
4. Ends with one recommended action if relevant

Be direct. Write as if presenting to a CFO."""

    payload = json.dumps({
        "model":      "claude-sonnet-4-20250514",
        "max_tokens": 300,
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
    result = generate_narrative()
    print(result["narrative"])
