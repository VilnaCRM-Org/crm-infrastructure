data "aws_iam_policy_document" "iam_policy_doc" {
  statement {
    sid    = "IAMCrmRolePolicy"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:GetRole",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:PassRole",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:ListInstanceProfilesForRole",
      "iam:TagRole",
      "iam:DeleteRole"
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:role/${var.project_name}-iam-for-lambda",
      "arn:aws:iam::${local.account_id}:role/${var.project_name}-staging-iam-for-lambda",
      "arn:aws:iam::${local.account_id}:role/${var.domain_name}-iam-role-replication",
      "arn:aws:iam::${local.account_id}:role/${var.domain_name}-staging-iam-role-replication"
    ]
  }
  statement {
    sid    = "IAMCrmPolicyRolePolicy"
    effect = "Allow"
    actions = [
      "iam:CreatePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
      "iam:TagPolicy",
      "iam:DeletePolicy"
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-staging-iam-policy-allow-sns-for-lambda",
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-iam-policy-allow-sns-for-lambda",
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-iam-policy-allow-logging-for-lambda",
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-staging-iam-policy-allow-logging-for-lambda",
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-staging-iam-policy-allow-logging-for-lambda",
      "arn:aws:iam::${local.account_id}:policy/${var.domain_name}-iam-role-policy-replication",
      "arn:aws:iam::${local.account_id}:policy/staging.${var.domain_name}-iam-role-policy-replication",
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-caching-policy",
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-canary-policy",
    ]
  }
  statement {
    sid    = "IAMPassRolePolicy"
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
    resources = ["arn:aws:iam::${local.account_id}:role/*"]
  }
} 