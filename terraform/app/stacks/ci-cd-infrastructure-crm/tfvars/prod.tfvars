project_name             = "crm-prod"
crm_infra_project_name   = "crm-infra-prod"
ci_cd_infra_project_name = "ci-cd-infra-crm-prod"
ci_cd_crm_project_name   = "ci-cd-crm-prod"
sandbox_project_name     = "sandbox-crm-prod"
environment              = "prod"
github_connection_name   = "Github"
source_repo_branch       = "main"
crm_repo_branch          = "main"
crm_url                  = "app.vilnacrm.com"
bucket_name              = "app.vilnacrm.com"

tags = {
  Project     = "crm-prod"
  Environment = "prod"
}

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
  { name = "batch-unit-mutation-lint", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "UnitMutationLintOutput" },
  { name = "deploy", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "DeployOutput" },
  { name = "healthcheck", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "HealthcheckOutput" },
  { name = "batch-lhci-leak", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "LHCILeakOutput" },
  { name = "batch-pw-load", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "PWLoadOutput" },
  { name = "release", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "ReleaseOutput" },
]

sandbox_stage_input = [
  { name = "up", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "UpOutput" },
  { name = "deploy", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "DeployOutput" },
  { name = "healthcheck", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "HealthcheckOutput" },
]

sandbox_deletion_stage_input = [
  { name = "delete", category = "Build", owner = "AWS", provider = "CodeBuild", input_artifacts = "SourceOutput", output_artifacts = "DeleteOutput" },
]