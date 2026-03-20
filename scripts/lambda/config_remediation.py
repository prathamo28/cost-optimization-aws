"""
config_remediation.py
---------------------
Triggered by AWS Config when a resource is found NON_COMPLIANT
with the required-tags rule.
Applies default tags to the resource and notifies the owner via SNS.
"""

import os
import json
import boto3

ec2 = boto3.client("ec2")
sns = boto3.client("sns")

SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
ENVIRONMENT   = os.environ["ENVIRONMENT"]
TEAM          = os.environ.get("DEFAULT_TEAM", "unowned")


def lambda_handler(event, context):
    """
    Config invokes this function with a list of non-compliant resources.
    We apply default tags to flag them and notify the owner.
    """
    invoking_event = json.loads(event.get("invokingEvent", "{}"))
    config_item    = invoking_event.get("configurationItem", {})

    if not config_item:
        print("No configuration item found in event.")
        return

    resource_type = config_item.get("resourceType", "")
    resource_id   = config_item.get("resourceId", "")
    existing_tags = config_item.get("tags", {})

    print(f"Non-compliant resource: {resource_type} / {resource_id}")

    # Apply missing mandatory tags with default values
    tags_to_apply = {}
    if not existing_tags.get("cost:team"):
        tags_to_apply["cost:team"] = TEAM
    if not existing_tags.get("cost:env"):
        tags_to_apply["cost:env"] = ENVIRONMENT
    if not existing_tags.get("cost:managed"):
        tags_to_apply["cost:managed"] = "terraform"

    if tags_to_apply and resource_type == "AWS::EC2::Instance":
        ec2.create_tags(
            Resources=[resource_id],
            Tags=[{"Key": k, "Value": v} for k, v in tags_to_apply.items()]
        )
        print(f"Applied tags to {resource_id}: {tags_to_apply}")

    # Notify regardless of whether we could tag it
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"[Cost] Untagged resource found — {resource_type}",
        Message=(
            f"Resource {resource_id} ({resource_type}) was found without mandatory cost tags.\n"
            f"Tags applied: {json.dumps(tags_to_apply)}\n"
            f"Existing tags: {json.dumps(existing_tags)}\n\n"
            f"Please update the Terraform configuration to include the correct tags for this resource."
        )
    )

    return {"resource_id": resource_id, "tags_applied": tags_to_apply}
