variable "project_name" {
  description = "Name of the project to be prefixed to create the s3 bucket"
  type        = string
}

variable "crm_project_name" {
  description = "Unique name for this Crm Codepipeline"
  type        = string
}

variable "ci_cd_project_name" {
  description = "Unique name for this CI/CD Codepipeline"
  type        = string
}

variable "ci_cd_crm_project_name" {
  description = "Unique name for this Crm Deploy Codepipeline"
  type        = string
}

variable "codepipeline_user_group_name" {
  description = "Unique name for this CI/CD User Group"
  type        = string
}

variable "codepipeline_user_group_path" {
  description = "Unique path for this CI/CD User Group"
  type        = string
}

variable "environment" {
  description = "Environment for this project"
  type        = string
}

variable "region" {
  description = "Region for this project"
  type        = string
}

variable "tags" {
  description = "Tags to be attached to the resource"
  type        = map(any)
}