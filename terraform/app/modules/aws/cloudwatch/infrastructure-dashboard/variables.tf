variable "crm_project_name" {
  description = "Unique name for the Crm Codepipeline"
  type        = string
}

variable "ci_cd_project_name" {
  description = "Unique name for the CI/CD Codepipeline"
  type        = string
}

variable "ci_cd_crm_project_name" {
  description = "Unique name for this Crm Deploy Codepipeline"
  type        = string
}

variable "region" {
  description = "Region for this project"
  type        = string
}

variable "environment" {
  description = "Environment for this project"
  type        = string
}