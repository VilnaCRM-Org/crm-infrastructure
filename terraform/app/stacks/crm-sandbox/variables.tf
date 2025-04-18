variable "project_name" {
  description = "Name for the project"
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

variable "s3_artifacts_bucket_files_deletion_days" {
  description = "Expiring time of files in buckets for lifecycle configuration rule"
  type        = number
}

variable "sandbox_bucket_name" {
  description = "Name for sandbox-crm bucket"
  type        = string
}

variable "tags" {
  description = "Tags to be associated with the S3 bucket"
  type        = map(any)
}