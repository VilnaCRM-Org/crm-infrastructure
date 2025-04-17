module "crm_policies" {
  source = "../../modules/aws/iam/policies/crm"

  project_name  = var.project_name
  policy_prefix = "${var.environment}-crm-user"
  region        = var.region
  environment   = var.environment
  domain_name   = var.domain_name

  tags = var.tags
}

module "crm_user_group" {
  source = "../../modules/aws/iam/user-groups/template"

  policy_arns = module.crm_policies.policy_arns
  group_name  = var.crm_user_group_name
  group_path  = var.crm_user_group_path

  depends_on = [module.crm_policies]
}

module "crm_user" {
  source = "../../modules/aws/iam/users/template"

  user_name = "crmUser"
  user_path = "/crm-users/"

  group_membership_name = "crm-group-membership"
  user_group_name       = module.crm_user_group.name

  tags = var.tags

  depends_on = [module.crm_user_group]
}