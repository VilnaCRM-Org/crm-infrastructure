variable "project_name" {
  description = "Unique name for this project"
  type        = string
}

variable "policy_prefix" {
  description = "Policy Prefix for policies"
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

variable "domain_name" {
  type        = string
  description = "Domain name for crm, used for all resources"
}

variable "tags" {
  description = "Tags to be attached to the resource"
  type        = map(any)
}

