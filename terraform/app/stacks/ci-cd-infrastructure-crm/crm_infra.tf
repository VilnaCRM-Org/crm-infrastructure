module "crm_infra_s3_artifacts_bucket" {
  source = "../../modules/aws/s3/codepipeline"

  project_name = var.crm_infra_project_name

  region      = var.region
  environment = var.environment

  s3_artifacts_bucket_files_deletion_days = var.s3_artifacts_bucket_files_deletion_days

  codepipeline_role_arn = module.crm_infra_codepipeline_iam_role.role_arn

  tags = var.tags
}

module "crm_infra_codepipeline_iam_role" {
  source = "../../modules/aws/iam/roles/codepipeline-role"

  project_name               = var.crm_infra_project_name
  codepipeline_iam_role_name = "${var.crm_infra_project_name}-codepipeline-role"

  source_repo_owner = var.source_repo_owner
  source_repo_name  = var.source_repo_name

  region      = var.region
  environment = var.environment

  crm_bucket_name = var.bucket_name

  s3_bucket_arn           = module.crm_infra_s3_artifacts_bucket.arn
  codestar_connection_arn = module.codestar_connection.arn

  policy_arns = module.crm_infra_policies.policy_arns

  tags = var.tags

  depends_on = [module.crm_infra_policies]
}

module "crm_infra_codebuild" {
  source = "../../modules/aws/codebuild/stages"

  project_name   = var.crm_infra_project_name
  build_projects = local.crm_infra_build_projects

  region      = var.region
  environment = var.environment

  s3_bucket_name = module.crm_infra_s3_artifacts_bucket.bucket
  role_arn       = module.crm_infra_codepipeline_iam_role.role_arn

  tags = var.tags

  depends_on = [
    module.crm_infra_s3_artifacts_bucket,
    module.crm_infra_codepipeline_iam_role,
    module.codestar_connection
  ]
}

module "crm_infra_codebuild_down" {
  source = "../../modules/aws/codebuild/project"

  project_name = local.crm_infra_codebuild_project_down_name

  region      = var.region
  environment = var.environment

  build_configuration = local.amazonlinux2_based_build
  env_variables       = local.crm_infra_build_project_down_env_variables

  source_configuration = local.crm_infra_codebuild_project_down_source_configuration

  role_arn = module.crm_infra_codepipeline_iam_role.role_arn

  tags = var.tags

  depends_on = [
    module.crm_infra_s3_artifacts_bucket,
    module.crm_infra_codepipeline_iam_role,
    module.codestar_connection
  ]
}

module "crm_infra_codepipeline" {
  source = "../../modules/aws/codepipeline/infrastructure"

  project_name       = var.crm_infra_project_name
  source_repo_owner  = var.source_repo_owner
  source_repo_name   = var.source_repo_name
  source_repo_branch = var.source_repo_branch
  detect_changes     = "true"

  stages = var.crm_infra_stage_input

  region = var.region

  s3_bucket_name          = module.crm_infra_s3_artifacts_bucket.bucket
  codepipeline_role_arn   = module.crm_infra_codepipeline_iam_role.role_arn
  codestar_connection_arn = module.codestar_connection.arn

  tags = var.tags

  depends_on = [module.crm_infra_codebuild, module.crm_infra_s3_artifacts_bucket]
}