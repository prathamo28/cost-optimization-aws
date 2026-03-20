"""
ebs_cleanup.py
--------------
Runs every Sunday at 02:00 UTC.
Finds EBS volumes that are not attached to any instance and snapshots
older than SNAPSHOT_AGE_DAYS. Notifies the owner before deleting.
"""

import os
import json
import boto3
from datetime import datetime, timezone, timedelta

ec2 = boto3.client("ec2")
sns = boto3.client("sns")

SNS_TOPIC_ARN     = os.environ["SNS_TOPIC_ARN"]
ENVIRONMENT       = os.environ["ENVIRONMENT"]
SNAPSHOT_AGE_DAYS = int(os.environ.get("SNAPSHOT_AGE_DAYS", "90"))


def lambda_handler(event, context):
    orphaned_volumes = find_orphaned_volumes()
    old_snapshots    = find_old_snapshots()

    report = {
        "orphaned_volumes": orphaned_volumes,
        "old_snapshots":    old_snapshots,
        "environment":      ENVIRONMENT,
        "run_date":         datetime.now(timezone.utc).isoformat(),
    }

    if orphaned_volumes or old_snapshots:
        notify(report)
        delete_snapshots(old_snapshots)

    print(json.dumps(report))
    return report


def find_orphaned_volumes():
    """Return volumes with no attachment and no cost:always-on tag."""
    response = ec2.describe_volumes(
        Filters=[
            {"Name": "status",          "Values": ["available"]},
            {"Name": "tag:cost:env",    "Values": [ENVIRONMENT]},
        ]
    )
    results = []
    for vol in response["Volumes"]:
        tags = {t["Key"]: t["Value"] for t in vol.get("Tags", [])}
        if tags.get("cost:always-on") == "true":
            continue
        results.append({
            "volume_id":   vol["VolumeId"],
            "size_gb":     vol["Size"],
            "created":     vol["CreateTime"].isoformat(),
            "owner_team":  tags.get("cost:team", "unknown"),
        })
    return results


def find_old_snapshots():
    """Return snapshots older than SNAPSHOT_AGE_DAYS with no associated AMI."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_AGE_DAYS)
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    snapshots = ec2.describe_snapshots(OwnerIds=[account_id])["Snapshots"]

    # Build set of snapshot IDs currently backing an AMI
    images = ec2.describe_images(Owners=[account_id])["Images"]
    ami_snapshot_ids = {
        mapping["Ebs"]["SnapshotId"]
        for img in images
        for mapping in img.get("BlockDeviceMappings", [])
        if "Ebs" in mapping
    }

    results = []
    for snap in snapshots:
        if snap["StartTime"] < cutoff and snap["SnapshotId"] not in ami_snapshot_ids:
            tags = {t["Key"]: t["Value"] for t in snap.get("Tags", [])}
            results.append({
                "snapshot_id": snap["SnapshotId"],
                "size_gb":     snap["VolumeSize"],
                "created":     snap["StartTime"].isoformat(),
                "owner_team":  tags.get("cost:team", "unknown"),
            })
    return results


def delete_snapshots(snapshots):
    """Delete old snapshots. Volumes are only reported, not deleted."""
    for snap in snapshots:
        try:
            ec2.delete_snapshot(SnapshotId=snap["snapshot_id"])
            print(f"Deleted snapshot {snap['snapshot_id']}")
        except Exception as e:
            print(f"Could not delete {snap['snapshot_id']}: {e}")


def notify(report):
    vol_count  = len(report["orphaned_volumes"])
    snap_count = len(report["old_snapshots"])

    lines = [
        f"EBS cleanup report — {ENVIRONMENT} — {report['run_date'][:10]}",
        "",
        f"Orphaned volumes found (not deleted, please review): {vol_count}",
    ]
    for v in report["orphaned_volumes"]:
        lines.append(f"  - {v['volume_id']}  {v['size_gb']}GB  owner: {v['owner_team']}")

    lines += [
        "",
        f"Old snapshots deleted (>{SNAPSHOT_AGE_DAYS} days, no AMI): {snap_count}",
    ]
    for s in report["old_snapshots"]:
        lines.append(f"  - {s['snapshot_id']}  {s['size_gb']}GB  owner: {s['owner_team']}")

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"[Cost] EBS cleanup — {vol_count} orphaned volumes, {snap_count} snapshots removed",
        Message="\n".join(lines),
    )
