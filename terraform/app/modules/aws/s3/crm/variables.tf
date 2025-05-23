variable "aws_cloudfront_distributions_arns" {
  type        = list(string)
  description = "CloudFront Distribution ARN"
}

variable "s3_logging_bucket_id" {
  type        = string
  description = "ID of the logging bucket"
}

variable "replication_s3_logging_bucket_id" {
  type        = string
  description = "ID of the logging bucket for the replication"
}

variable "path_to_site_content" {
  type        = string
  description = "ID of the logging bucket"
  default     = "../../../../../.."
}

variable "path_to_lambdas" {
  type        = string
  description = "ID of the logging bucket"
  default     = "../../../../../../aws/lambda"
}

variable "domain_name" {
  type        = string
  description = "Domain name for crm, used for all resources"
}

variable "project_name" {
  description = "Name of the project to be prefixed to create the s3 bucket"
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

variable "s3_bucket_custom_name" {
  type        = string
  description = "Any non-empty string here will replace default name of bucket `var.domain_name`"
}

variable "lambda_configuration" {
  description = "Lambda Configuration Variables"
  type        = map(any)
}

variable "cloudwatch_log_group_retention_days" {
  description = "Retention time of Cloudwatch log group logs"
  type        = number
}

variable "staging" {
  type        = string
  description = "Domain name for crm, used for all resources"
}

variable "tags" {
  description = "Tags to be associated with the S3 bucket"
  type        = map(any)
}
