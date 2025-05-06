data "aws_iam_policy_document" "iam_policy_doc" {
  statement {
    sid    = "IAMCodePipelineRolePolicy"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:GetRole",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:AttachRolePolicy",
      "iam:PassRole",
      "iam:DetachRolePolicy",
      "iam:ListInstanceProfilesForRole",
      "iam:TagRole",
      "iam:DeleteRole"
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:role/${var.crm_project_name}-codepipeline-role",
      "arn:aws:iam::${local.account_id}:role/${var.ci_cd_project_name}-codepipeline-role",
      "arn:aws:iam::${local.account_id}:role/${var.ci_cd_crm_project_name}-codepipeline-role",
      "arn:aws:iam::${local.account_id}:role/${var.ci_cd_crm_project_name}-codebuild-rollback-role",
      "arn:aws:iam::${local.account_id}:role/${var.ci_cd_crm_project_name}-iam-for-lambda",
      "arn:aws:iam::${local.account_id}:role/reports-crm-chatbot-channel-role",
      "arn:aws:iam::${local.account_id}:role/crm-infrastructure-trigger-role",
      "arn:aws:iam::${local.account_id}:role/crm-deploy-trigger-role",
      "arn:aws:iam::${local.account_id}:role/sandbox-crm-deletion-trigger-role",
      "arn:aws:iam::${local.account_id}:role/sandbox-crm-creation-trigger-role",
      "arn:aws:iam::${local.account_id}:role/ci-cd-infra-crm-trigger-role",
      "arn:aws:iam::${local.account_id}:role/github-actions-crm-role",
      "arn:aws:iam::${local.account_id}:role/crm-${var.environment}-codepipeline-role-sandbox-crm-deletion-${var.environment}",
      "arn:aws:iam::${local.account_id}:role/crm-${var.environment}-codebuild-role-sandbox-crm-deletion-${var.environment}",
      "arn:aws:iam::${local.account_id}:role/sandbox-crm-cleanup-function-role",
      "arn:aws:iam::${local.account_id}:role/ci-cd-crm-${var.environment}-github-oidc-codepipeline-role"
    ]
  }
  statement {
    sid    = "IAMCodePipelinePolicyRolePolicy"
    effect = "Allow"
    actions = [
      "iam:CreatePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
      "iam:CreatePolicyVersion",
      "iam:TagPolicy",
      "iam:DeletePolicyVersion",
      "iam:DeletePolicy"
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:policy/${var.crm_project_name}-codepipeline-policy",
      "arn:aws:iam::${local.account_id}:policy/${var.ci_cd_project_name}-codepipeline-policy",
      "arn:aws:iam::${local.account_id}:policy/${var.ci_cd_project_name}-iam-policy-allow-logging-for-cloudtrail",
      "arn:aws:iam::${local.account_id}:policy/${var.ci_cd_crm_project_name}-codepipeline-policy",
      "arn:aws:iam::${local.account_id}:policy/${var.ci_cd_crm_project_name}-codebuild-rollback-role-policy",
      "arn:aws:iam::${local.account_id}:policy/${var.ci_cd_crm_project_name}-iam-policy-allow-sns-for-lambda",
      "arn:aws:iam::${local.account_id}:policy/${var.ci_cd_crm_project_name}-iam-policy-allow-logging-for-lambda",
      "arn:aws:iam::${local.account_id}:policy/SandBoxPolicies/${var.environment}-sandbox-crm-s3-policy",
      "arn:aws:iam::${local.account_id}:policy/SandBoxPolicies/${var.environment}-sandbox-crm-general-policy",
      "arn:aws:iam::${local.account_id}:policy/token-secrets-access-policy",
      "arn:aws:iam::${local.account_id}:policy/crm-${var.environment}-codepipeline-policy",
      "arn:aws:iam::${local.account_id}:policy/crm-${var.environment}-codebuild-policy",
      "arn:aws:iam::${local.account_id}:policy/crm-deploy-trigger-role-policy",
      "arn:aws:iam::${local.account_id}:policy/crm-infrastructure-trigger-role-policy",
      "arn:aws:iam::${local.account_id}:policy/sandbox-crm-${var.environment}-codepipeline-role-policy",
      "arn:aws:iam::${local.account_id}:policy/sandbox-crm-creation-trigger-role-policy",
      "arn:aws:iam::${local.account_id}:policy/sandbox-crm-deletion-trigger-role-policy",
      "arn:aws:iam::${local.account_id}:policy/sandbox-crm-cleanup-function-policy"
    ]
  }
  statement {
    sid    = "IAMPassRolePolicy"
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/*"]
  }
  statement {
    sid    = "ChatbotIAMPolicy"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:GetRole",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:AttachRolePolicy",
      "iam:PassRole",
      "iam:DetachRolePolicy",
      "iam:ListInstanceProfilesForRole",
      "iam:TagRole",
      "iam:DeleteRole"
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:role/codepipeline-crm-chatbot-channel-role",
      "arn:aws:iam::${local.account_id}:role/ci-cd-alerts-crm-chatbot-channel-role",
      "arn:aws:iam::${local.account_id}:role/reports-crm-chatbot-channel-role",
      "arn:aws:iam::${local.account_id}:role/${var.ci_cd_project_name}-iam-for-cloudtrail"
    ]
  }
} 