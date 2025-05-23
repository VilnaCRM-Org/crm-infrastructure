data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_iam_policy_document" "general_policy_doc" {
  statement {
    sid    = "GeneralPolicy"
    effect = "Allow"
    actions = [
      "sts:GetCallerIdentity"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "TerraformStateListS3Policy"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketTagging"
    ]
    resources = ["arn:aws:s3:::terraform-state-${local.account_id}-${var.region}-${var.environment}"]
  }

  statement {
    sid    = "DynamoDBStatePolicy"
    effect = "Allow"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:DescribeContinuousBackups",
      "dynamodb:DescribeTimeToLive",
      "dynamodb:ListTagsOfResource",
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:DeleteItem"
    ]
    resources = ["arn:aws:dynamodb:${var.region}:${local.account_id}:table/terraform_crm_locks"]
  }

  statement {
    sid    = "TerraformStateGetS3Policy"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject"
    ]
    resources = ["arn:aws:s3:::terraform-state-${local.account_id}-${var.region}-${var.environment}/main/${var.region}/${var.environment}/stacks/crm-sandbox-crm/terraform.tfstate"]
  }
} 