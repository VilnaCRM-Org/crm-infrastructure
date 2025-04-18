module "iam_roles" {
  source                  = "../../modules/aws/iam/roles/sandbox-crm-deletion-role"
  project_name            = var.project_name
  environment             = var.environment
  region                  = var.region
  account_id              = data.aws_caller_identity.current.account_id
  codestar_connection_arn = module.codestar_connection.arn
  BRANCH_NAME             = var.BRANCH_NAME
}

module "s3_buckets" {
  source       = "../../modules/aws/s3/sandbox-crm-deletion"
  project_name = var.project_name
  environment  = var.environment

  s3_artifacts_bucket_files_deletion_days = var.s3_artifacts_bucket_files_deletion_days

  tags = var.tags
}

module "codebuild_sandbox_deletion" {
  source         = "../../modules/aws/codebuild/stages"
  project_name   = local.project_name
  role_arn       = module.iam_roles.codebuild_role_arn
  build_projects = local.sandbox_delete_projects
  s3_bucket_name = module.s3_buckets.codebuild_logs_bucket_name
  environment    = var.environment
  region         = var.region
  tags           = var.tags


  depends_on = [module.iam_roles, module.s3_buckets]
}

module "codepipeline_sandbox_deletion" {
  source = "../../modules/aws/codepipeline/sandbox-crm"

  codepipeline_name = "${var.sandbox_buildspecs}-deletion"

  project_name = local.project_name

  source_repo_owner  = var.source_repo_owner
  source_repo_name   = var.source_repo_name
  source_repo_branch = var.source_repo_branch

  PR_NUMBER       = var.PR_NUMBER
  BRANCH_NAME     = var.BRANCH_NAME
  IS_PULL_REQUEST = var.IS_PULL_REQUEST

  lambda_python_version                 = var.lambda_python_version
  lambda_reserved_concurrent_executions = var.lambda_reserved_concurrent_executions

  detect_changes = false

  stages = var.sandbox_deletion_stage_input

  region = local.region

  codepipeline_role_arn   = module.iam_roles.codepipeline_role_arn
  s3_bucket_name          = module.s3_buckets.codepipeline_bucket_name
  codestar_connection_arn = module.codestar_connection.arn

  notification_rule_suffix = "deletion"

  tags = var.tags

  depends_on = [module.s3_buckets, module.codebuild_sandbox_deletion, module.iam_roles]
}

module "sandbox_deletion_pipeline_role" {
  source       = "../../modules/aws/iam/oidc/pipeline-trigger-role"
  role_name    = "${var.sandbox_buildspecs}-deletion-trigger-role"
  github_owner = var.source_repo_owner
  github_repo  = var.source_repo_name
  crm_repo     = var.crm_content_repo_name
  branch       = var.source_repo_branch
  pipeline_arn = module.codepipeline_sandbox_deletion.arn
}