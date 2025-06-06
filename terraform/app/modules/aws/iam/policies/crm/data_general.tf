data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_iam_policy_document" "general_policy_doc" {
  statement {
    sid    = "GeneralPolicy"
    effect = "Allow"
    actions = [
      "sts:GetCallerIdentity",
      "route53:ListHostedZones",
      "cloudfront:CreateOriginAccessControl",
      "acm:RequestCertificate",
      "iam:CreateServiceLinkedRole",
      "iam:ListRoles",
      "s3:ListAllMyBuckets",
      "s3:GetBucketLocation",
      "xray:GetTraceSummaries",
      "xray:BatchGetTraces",
      "apigateway:GET",
      "logs:DescribeLogGroups",
      "logs:CreateLogDelivery",
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:DisassociateKmsKey",
      "synthetics:*"
    ]
    #checkov:skip=CKV_AWS_356:Required by AWSCC module and wafv2 logging
    #checkov:skip=CKV_AWS_109:Required by AWSCC module and wafv2 logging
    #checkov:skip=CKV_AWS_111:Required by AWSCC module and wafv2 logging
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
    sid    = "CloudWatchDashboardPolicy"
    effect = "Allow"
    actions = [
      "cloudwatch:ListDashboards",
      "cloudwatch:GetDashboard",
      "cloudwatch:PutDashboard",
      "cloudwatch:DeleteDashboards",
    ]
    resources = [
      "arn:aws:cloudwatch::${local.account_id}:dashboard/${var.project_name}-dashboard"
    ]
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
    resources = ["arn:aws:s3:::terraform-state-${local.account_id}-${var.region}-${var.environment}/main/${var.region}/${var.environment}/stacks/crm/terraform.tfstate"]
  }
  statement {
    sid    = "CloudwatchAlarmsPolicy"
    effect = "Allow"
    actions = [
      "cloudwatch:DescribeAlarms",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:ListTagsForResource"
    ]
    resources = [
      "arn:aws:cloudwatch:*:*:alarm:*"
    ]
  }

  statement {
    sid    = "AllowCloudFrontFunctionManagement"
    effect = "Allow"
    actions = [
      "cloudfront:UpdateFunction",
      "cloudfront:DescribeFunction",
      "cloudfront:GetFunction",
      "cloudfront:CreateFunction",
      "cloudfront:PublishFunction",
      "cloudfront:DeleteFunction"
    ]
    resources = ["arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:function/crm-routing-function"]
  }

  statement {
    sid    = "CloudwatchAlarmsReadWritePolicy"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DeleteAlarms"
    ]
    resources = [
      "arn:aws:cloudwatch:*:*:alarm:Synthetics-*"
    ]
  }
  statement {
    sid    = "CodePipelinePolicy"
    effect = "Allow"
    actions = [
      "codepipeline:StartPipelineExecution",
    ]
    resources = [
      "arn:aws:codepipeline:${var.region}:${local.account_id}:ci-cd-crm-${var.environment}-pipeline"
    ]
  }
} 