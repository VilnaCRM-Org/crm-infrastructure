variable "project_name" {
  description = "Unique name for the project"
  type        = string
}

variable "source_repo_owner" {
  description = "Source repo owner of the GitHub repository"
  type        = string
}

variable "source_repo_name" {
  description = "Infrastructure Source repo name of the repository"
  type        = string
}

variable "environment" {
  description = "Environment for the project"
  type        = string
}

variable "ci_cd_crm_codepipeline_arn" {
  description = "CodePipeline ARN of CI/CD Crm pipeline"
  type        = string
}

variable "ci_cd_crm_codepipeline_name" {
  description = "CodePipeline Name of CI/CD Crm pipeline"
  type        = string
}

variable "sandbox_codepipeline_arn" {
  description = "CodePipeline ARN of sandbox-crm pipeline"
  type        = string
}

variable "sandbox_codepipeline_name" {
  description = "CodePipeline Name of sandbox-crm pipeline"
  type        = string
}

variable "tags" {
  description = "Tags to be attached to the resource"
  type        = map(any)
}
