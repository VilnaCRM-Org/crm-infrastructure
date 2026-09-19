mock_provider "aws" {}

mock_provider "aws" {
  alias = "us-east-1"

  mock_data "aws_wafv2_web_acl" {
    defaults = {
      arn = "arn:aws:wafv2:us-east-1:123456789012:global/webacl/wafv2-web-acl/00000000-0000-0000-0000-000000000000"
    }
  }
}

variables {
  aws_s3_bucket_this_bucket_regional_domain_name        = "app.example.com.s3.eu-central-1.amazonaws.com"
  aws_s3_bucket_replication_bucket_regional_domain_name = "app.example.com-replication.s3.eu-west-1.amazonaws.com"
  domain_name                                           = "app.example.com"
  project_name                                          = "crm-test"
  tags                                                  = {}
  aws_acm_certificate_id                                = "00000000-0000-0000-0000-000000000000"
  aws_acm_certificate_arn                               = "arn:aws:acm:us-east-1:123456789012:certificate/00000000-0000-0000-0000-000000000000"
  enable_cloudfront_staging                             = true
  enable_access_logging                                 = false
  enable_cloudwatch_alarms                              = true
  enable_waf                                            = true
  cloudfront_custom_error_responses                     = []
  cloudfront_configuration = {
    price_class                = "PriceClass_100"
    min_ttl                    = 0
    default_ttl                = 86400
    max_ttl                    = 31536000
    access_control_max_age_sec = 31536000
    default_root_object        = "index.html"
    minimum_protocol_version   = "TLSv1.2_2021"
  }
}

run "default_keeps_protection_and_essential_alarms" {
  command = plan
  assert {
    condition     = length(aws_wafv2_web_acl.waf_web_acl) == 1 && length(data.aws_wafv2_web_acl.shared) == 0
    error_message = "Default rollout must retain the dedicated WAF without a cross-stack lookup."
  }
  assert {
    condition     = length(aws_cloudwatch_metric_alarm.cloudfront_origin_latency) == 0 && length(aws_cloudwatch_metric_alarm.cloudfront_staging_origin_latency) == 0 && length(aws_cloudwatch_metric_alarm.cloudfront_500_errors) == 1 && length(aws_cloudwatch_metric_alarm.cloudfront_staging_500_errors) == 1
    error_message = "Remove unsubscribed latency alarms while preserving primary and staging 5xx alarms."
  }
}

run "test_does_not_discover_or_create_waf" {
  command = plan
  variables {
    enable_waf               = false
    shared_waf_web_acl_name  = "wafv2-web-acl"
    enable_cloudwatch_alarms = false
  }
  assert {
    condition     = length(aws_wafv2_web_acl.waf_web_acl) == 0 && length(data.aws_wafv2_web_acl.shared) == 0 && aws_cloudfront_distribution.this.web_acl_id == null
    error_message = "WAF-disabled environments must not need a website-owned ACL."
  }
}

run "switch_retains_old_waf_and_log_history" {
  command = plan
  variables {
    shared_waf_web_acl_name             = "wafv2-web-acl"
    enable_cloudfront_staging           = false
    attach_continuous_deployment_policy = false
  }
  assert {
    condition     = aws_cloudfront_distribution.this.web_acl_id == data.aws_wafv2_web_acl.shared[0].arn && length(aws_wafv2_web_acl.waf_web_acl) == 1 && length(aws_wafv2_web_acl_logging_configuration.waf_web_acl_logging) == 1 && length(aws_cloudwatch_log_group.waf_web_acl_log_group) == 1
    error_message = "Switch must retain the old ACL, logging and historical log group."
  }
  assert {
    condition     = aws_cloudfront_distribution.this.continuous_deployment_policy_id == "" && length(aws_cloudfront_continuous_deployment_policy.continuous_deployment_policy) == 0
    error_message = "The switch phase must not attach a continuous deployment policy."
  }
}

run "cleanup_removes_only_duplicate_protection" {
  command = plan
  variables {
    shared_waf_web_acl_name = "wafv2-web-acl"
    retain_dedicated_waf    = false
  }
  assert {
    condition     = length(aws_wafv2_web_acl.waf_web_acl) == 0 && length(aws_wafv2_web_acl_logging_configuration.waf_web_acl_logging) == 0 && length(aws_cloudwatch_log_group.waf_web_acl_log_group) == 1
    error_message = "Cleanup removes the duplicate ACL and logging configuration but preserves historical logs."
  }
  assert {
    condition     = aws_cloudfront_distribution.this.web_acl_id == data.aws_wafv2_web_acl.shared[0].arn && aws_cloudfront_distribution.staging_cloudfront_distribution[0].web_acl_id == data.aws_wafv2_web_acl.shared[0].arn
    error_message = "Both distributions must stay protected by the shared ACL."
  }
}
