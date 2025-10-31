resource "awscc_chatbot_slack_channel_configuration" "slack_channel_configuration" {
  configuration_name = "${var.project_name}-crm-slack-conf"
  iam_role_arn       = awscc_iam_role.chatbot_role.arn
  slack_channel_id   = var.channel_id
  slack_workspace_id = var.workspace_id
  sns_topic_arns     = var.sns_topic_arns
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

#checkov:skip=CKV_AWS_356:Chatbot requires wildcard access to discover and read all pipelines for monitoring purposes
data "aws_iam_policy_document" "chatbot_codepipeline_policy" {
  statement {
    sid    = "CodePipelineReadOnly"
    effect = "Allow"
    actions = [
      "codepipeline:GetPipeline",
      "codepipeline:GetPipelineState",
      "codepipeline:GetPipelineExecution",
      "codepipeline:ListPipelines",
      "codepipeline:ListPipelineExecutions",
      "codepipeline:ListActionExecutions",
      "codepipeline:ListTagsForResource"
    ]
    resources = [
      "arn:aws:codepipeline:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:*"
    ]
  }

  statement {
    sid    = "CodePipelineExecutionControl"
    effect = "Allow"
    actions = [
      "codepipeline:StartPipelineExecution",
      "codepipeline:StopPipelineExecution"
    ]
    resources = [
      "arn:aws:codepipeline:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:*"
    ]
  }
}

resource "awscc_iam_role" "chatbot_role" {
  role_name = "${var.project_name}-crm-chatbot-channel-role"
  assume_role_policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "chatbot.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
    ]
  })
  managed_policy_arns = [
    "arn:aws:iam::aws:policy/AWSResourceExplorerReadOnlyAccess",
    "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
  ]
  policies = [
    {
      policy_document = data.aws_iam_policy_document.chatbot_codepipeline_policy.json
      policy_name     = "${var.project_name}-crm-chatbot-codepipeline-policy"
    }
  ]
}
