output "github_token_secret_arn" {
  value       = module.github_token_secret.secret_arn
  description = "ARN of the GitHub token secret"
}

output "crm_infra_pipeline_name" {
  value       = module.crm_infra_codepipeline.name
  description = "CRM infrastructure pipeline started after the CI/CD infrastructure apply"
}
