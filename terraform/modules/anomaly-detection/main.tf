# =============================================================================
# Module: anomaly-detection
# AWS Cost Anomaly Detection — ML-based, learns normal spend patterns
# No fixed thresholds — adapts automatically as the account grows
# =============================================================================

resource "aws_ce_anomaly_monitor" "service" {
  name              = "${var.name_prefix}-anomaly-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
  tags              = var.tags
}

resource "aws_ce_anomaly_subscription" "alerts" {
  name      = "${var.name_prefix}-anomaly-alerts"
  frequency = "IMMEDIATE"
  tags      = var.tags

  monitor_arn_list = [aws_ce_anomaly_monitor.service.arn]

  subscriber {
    type    = "SNS"
    address = var.sns_topic_arn
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_PERCENTAGE"
      values        = [tostring(var.anomaly_threshold_percentage)]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
}
