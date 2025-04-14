module "infrastructure_dashboard" {
  source = "../../modules/aws/cloudwatch/infrastructure-dashboard"

  crm_project_name       = var.crm_infra_project_name
  ci_cd_project_name     = var.ci_cd_infra_project_name
  ci_cd_crm_project_name = var.ci_cd_crm_project_name


  region      = var.region
  environment = var.environment
}