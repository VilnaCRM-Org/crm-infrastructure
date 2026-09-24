output "DOMAIN_NAME" {
  description = "Crm endpoint"
  value       = var.domain_name
}

output "WAF_MIGRATION_IN_PROGRESS" {
  description = "Suppress downstream application deployment while CloudFront/WAF migration is between stable stages"
  value       = var.enable_waf && (!var.attach_continuous_deployment_policy || !var.enable_cloudfront_staging || (var.shared_waf_web_acl_name != null && var.retain_dedicated_waf))
}

output "PRODUCTION_DISTRIBUTION_ID" {
  description = "Distribution ID"
  value       = module.cloudfront.id
}

output "CONTINUOUS_DEPLOYMENT_ID" {
  description = "CD ID"
  value       = module.cloudfront.continuous_deployment_id
}
