project_name             = "crm-test"
crm_infra_project_name   = "crm-infra-test"
ci_cd_infra_project_name = "ci-cd-infra-crm-test"
ci_cd_crm_project_name   = "ci-cd-crm-test"
sandbox_project_name     = "sandbox-crm-test"
environment              = "test"
github_connection_name   = "Github"
source_repo_branch       = "main"
crm_repo_branch          = "main"
crm_url                  = "app.vilnacrmtest.com"
bucket_name              = "app.vilnacrmtest.com"

tags = {
  Project     = "crm-test"
  Environment = "test"
}

s3_artifacts_bucket_files_deletion_days = 1

s3_logs_lifecycle_configuration = {
  standard_ia_transition_days  = 0
  glacier_transition_days      = 0
  deep_archive_transition_days = 0
  deletion_days                = 30
}

enable_cloudwatch_alarms = false

ci_cd_infra_stage_input = [
  { name = "validate", category = "Test", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "ValidateOutput" },
  { name = "plan", category = "Test", owner = "AWS", provider = "CodeBuild", input_artifacts = "ValidateOutput", output_artifacts = "PlanOutput" },
  { name = "up", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "PlanOutput", output_artifacts = "UpOutput" },
]

crm_infra_stage_input = [
  { name = "validate", category = "Test", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "ValidateOutput" },
  { name = "plan", category = "Test", owner = "AWS", provider = "CodeBuild", input_artifacts = "ValidateOutput", output_artifacts = "PlanOutput" },
  { name = "up", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "PlanOutput", output_artifacts = "UpOutput" },
]

ci_cd_crm_stage_input = [
  { name = "deploy", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "DeployOutput" },
  { name = "healthcheck", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "HealthcheckOutput" },
  { name = "release", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "ReleaseOutput" },
]

sandbox_stage_input = [
  { name = "up", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "UpOutput" },
  { name = "deploy", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "DeployOutput" },
  { name = "healthcheck", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "HealthcheckOutput" },
]

sandbox_deletion_stage_input = [
  { name = "delete", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "DeleteOutput" }
]
