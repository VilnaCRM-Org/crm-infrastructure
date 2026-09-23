variable "project_name" {
  description = "Unique name for this project"
  type        = string
}

variable "source_repo_owner" {
  description = "Source repo owner of the GitHub repository"
  type        = string
}

variable "source_repo_name" {
  description = "Source repo name of the GitHub repository"
  type        = string
}

variable "source_repo_branch" {
  description = "Default branch in the Source repo for which CodePipeline needs to be configured"
  type        = string
}

variable "crm_content_repo_name" {
  description = "CRM application repository captured in each pipeline execution"
  type        = string
}

variable "crm_repo_branch" {
  description = "CRM application branch that triggers content deployments"
  type        = string
}

variable "region" {
  description = "Region for this project"
  type        = string
}

variable "s3_bucket_name" {
  description = "S3 bucket name to be used for storing the artifacts"
  type        = string
}

variable "codepipeline_role_arn" {
  description = "ARN of the codepipeline IAM role"
  type        = string
}

variable "codestar_connection_arn" {
  description = "The ARN of the CodeStar connection"
  type        = string
}

variable "detect_changes" {
  description = "Specyfing changes detection"
  type        = string
}

variable "lambda_python_version" {
  description = "Python version for Lambda"
  type        = string
}

variable "lambda_reserved_concurrent_executions" {
  description = "Function-level concurrent execution Limit for Lambda"
  type        = number
}

variable "path_to_lambdas" {
  type        = string
  description = "ID of the logging bucket"
  default     = "../../../../../../aws/lambda"
}

variable "tags" {
  description = "Tags to be attached to the CodePipeline"
  type        = map(any)
}

variable "stages" {
  description = "Ordered CRM actions: independent core tests, then one exclusive deployment-through-release stage"
  type = list(object({
    name             = string
    category         = string
    owner            = string
    provider         = string
    input_artifacts  = list(string)
    output_artifacts = string
  }))

  validation {
    condition     = join(",", var.stages[*].name) == "batch-unit-mutation-lint,deploy,healthcheck,batch-lhci-leak,batch-pw-load,release"
    error_message = "CRM actions must retain core tests, deploy, healthcheck, Lighthouse/memory, Playwright/load, and release in that order."
  }
}

variable "cloudwatch_alerts_sns_topic_arn" {
  description = "ARN of Alerts SNS Topic"
  type        = string
}

variable "cloudwatch_log_group_retention_days" {
  description = "Retention time of Cloudwatch log group logs"
  type        = number
}

variable "enable_cloudwatch_alarms" {
  description = "Whether to create CloudWatch alarms for the crm pipeline"
  type        = bool
}
