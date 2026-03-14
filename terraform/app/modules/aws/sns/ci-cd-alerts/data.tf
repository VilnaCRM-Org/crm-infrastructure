data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_iam_policy_document" "cloudwatch_alerts_sns_topic_doc" {
  count = length(var.cloudwatch_alarms_arns) > 0 ? 1 : 0

  statement {
    sid     = "AllowSNSPublishIntoTopicForCloudWatch"
    effect  = "Allow"
    actions = ["sns:Publish"]

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    resources = ["${aws_sns_topic.cloudwatch_alerts_notifications.arn}"]

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = var.cloudwatch_alarms_arns
    }
  }
}
