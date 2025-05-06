data "aws_iam_policy_document" "lambda_policy_doc" {
  statement {
    sid    = "LambdaPolicy"
    effect = "Allow"
    actions = [
      "lambda:CreateFunction",
      "lambda:GetFunction",
      "lambda:ListVersionsByFunction",
      "lambda:GetFunctionCodeSigningConfig",
      "lambda:UpdateFunctionConfiguration",
      "lambda:AddPermission",
      "lambda:GetPolicy",
      "lambda:RemovePermission",
      "lambda:DeleteFunction"
    ]
    resources = [
      "arn:aws:lambda:${var.region}:${local.account_id}:function:${var.ci_cd_crm_project_name}-reports-notification",
      "arn:aws:lambda:${var.region}:${local.account_id}:function:sandbox-crm-cleanup-lambda",
    ]
  }
} 