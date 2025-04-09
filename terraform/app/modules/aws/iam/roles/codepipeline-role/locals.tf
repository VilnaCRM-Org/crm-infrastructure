locals {
  account_id               = data.aws_caller_identity.current.account_id
  is_ci_cd_infra           = var.project_name == "ci-cd-infra-crm-${var.environment}" ? true : false
  is_crm_infra         = var.project_name == "crm-infra-${var.environment}" ? true : false
  policy_arns              = [for key, policy in var.policy_arns : policy.arn]
  ci_cd_infra_arns         = { for key, policy in var.policy_arns : key => policy if startswith(key, "ci_cd_infra_") }
  crm_infra_arns       = { for key, policy in var.policy_arns : key => policy if startswith(key, "crm_infra_") }
  crm_bucket_arn       = "arn:aws:s3:::${var.crm_bucket_name}"
  crm_bucket_files_arn = "arn:aws:s3:::${var.crm_bucket_name}/*"
}

locals {
  ci_cd_infra_codepipeline_policy_bucket_access = [
    "${var.s3_bucket_arn}/*",
    "${var.s3_bucket_arn}"
  ]
  crm_infra_codepipeline_policy_bucket_access = [
    "${var.s3_bucket_arn}/*",
    "${var.s3_bucket_arn}",
    "${local.crm_bucket_arn}",
    "${local.crm_bucket_files_arn}"
  ]
}