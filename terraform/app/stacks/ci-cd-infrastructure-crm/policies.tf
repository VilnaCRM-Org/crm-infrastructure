module "ci_cd_infra_policies" {
  source = "../../modules/aws/iam/policies/codepipeline"

  policy_prefix = "${var.environment}-ci-cd-infra-crm"

  project_name               = var.project_name
  crm_project_name       = var.crm_infra_project_name
  ci_cd_project_name         = var.ci_cd_infra_project_name
  ci_cd_crm_project_name = var.ci_cd_crm_project_name

  region      = var.region
  environment = var.environment

  tags = var.tags
}

module "crm_infra_policies" {
  source = "../../modules/aws/iam/policies/crm"

  project_name  = var.project_name
  policy_prefix = "${var.environment}-crm-infra"
  region        = var.region
  environment   = var.environment
  domain_name   = var.crm_url

  tags = var.tags
}

module "sandbox_policies" {
  source = "../../modules/aws/iam/policies/sandbox-crm"

  project_name  = var.sandbox_project_name
  policy_prefix = "${var.environment}-sandbox-crm"
  region        = var.region
  environment   = var.environment

  tags = var.tags
}