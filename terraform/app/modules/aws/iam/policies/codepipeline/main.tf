resource "aws_iam_policy" "sns_policy" {
  name        = "${var.policy_prefix}-sns-policy"
  policy      = data.aws_iam_policy_document.sns_policy_doc.json
  path        = "/CodePipelinePolicies/"
  description = "Policy to allow to use SNS"

  tags = var.tags
}

resource "aws_iam_policy" "s3_policy" {
  name        = "${var.policy_prefix}-s3-policy"
  policy      = data.aws_iam_policy_document.s3_policy_doc.json
  path        = "/CodePipelinePolicies/"
  description = "Policy to allow to use S3"

  tags = var.tags
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.policy_prefix}-lambda-policy"
  policy      = data.aws_iam_policy_document.lambda_policy_doc.json
  path        = "/CodePipelinePolicies/"
  description = "Policy to allow to use Lambda"

  tags = var.tags
}

resource "aws_iam_policy" "iam_policy" {
  name        = "${var.policy_prefix}-iam-policy"
  policy      = data.aws_iam_policy_document.iam_policy_doc.json
  path        = "/CodePipelinePolicies/"
  description = "Policy to allow to use IAM"

  tags = var.tags
}

resource "aws_iam_policy" "general_policy" {
  name        = "${var.policy_prefix}-general-policy"
  policy      = data.aws_iam_policy_document.general_policy_doc.json
  path        = "/CodePipelinePolicies/"
  description = "Policy to allow to use general features"

  tags = var.tags
}

resource "aws_iam_policy" "codepipeline_policy" {
  name        = "${var.policy_prefix}-codepipeline-policy"
  policy      = data.aws_iam_policy_document.codepipeline_policy_doc.json
  path        = "/CodePipelinePolicies/"
  description = "Policy to allow to use CodePipeline related resources"

  tags = var.tags
}
