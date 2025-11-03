module "cloudfront" {
  source = "../../modules/aws/cloudfront"

  domain_name  = var.domain_name
  project_name = var.project_name

  aws_s3_bucket_this_bucket_regional_domain_name        = module.s3_bucket.bucket_regional_domain_name
  aws_s3_bucket_replication_bucket_regional_domain_name = module.s3_bucket.replication_bucket_regional_domain_name


  aws_acm_certificate_arn = module.dns.arn
  aws_acm_certificate_id  = module.dns.id

  logging_bucket_domain_name = module.logging_s3_bucket.bucket_domain_name

  cloudfront_configuration          = var.cloudfront_configuration
  cloudfront_custom_error_responses = var.cloudfront_custom_error_responses

  enable_cloudfront_staging = var.enable_cloudfront_staging

  continuous_deployment_policy_type   = var.continuous_deployment_policy_type
  continuous_deployment_policy_weight = var.continuous_deployment_policy_weight
  continuous_deployment_policy_header = var.continuous_deployment_policy_header

  tags = var.tags
}
