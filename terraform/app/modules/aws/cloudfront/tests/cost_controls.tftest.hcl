mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

mock_provider "aws" {
  alias = "us-east-1"

  # Stateful mock runs need schema-valid computed values at apply time.
  mock_resource "aws_cloudfront_function" {
    defaults = {
      arn = "arn:aws:cloudfront::123456789012:function/crm-routing-function"
    }
  }

  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:us-east-1:123456789012:crm-cloudwatch-alarm-notifications"
    }
  }

  mock_resource "aws_cloudwatch_log_group" {
    defaults = {
      arn = "arn:aws:logs:us-east-1:123456789012:log-group:aws-waf-logs-crm"
    }
  }

  mock_resource "aws_wafv2_web_acl" {
    defaults = {
      arn = "arn:aws:wafv2:us-east-1:123456789012:global/webacl/wafv2-web-acl-crm/11111111-1111-1111-1111-111111111111"
    }
  }

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

# A fresh plan cannot detect ignore_changes suppressing an update. Seed mock
# state, then exercise attachment changes on the existing primary distribution.
# All applies here use mock_provider; they never call AWS.
run "seed_attached_primary" {
  command = apply
  assert {
    condition     = aws_cloudfront_distribution.this.continuous_deployment_policy_id == aws_cloudfront_continuous_deployment_policy.continuous_deployment_policy[0].id
    error_message = "The initial primary must have its Terraform-owned policy attached."
  }
}

run "detach_existing_primary_keeps_staging_and_waf" {
  command = plan
  variables {
    attach_continuous_deployment_policy = false
  }
  assert {
    condition     = aws_cloudfront_distribution.this.continuous_deployment_policy_id == ""
    error_message = "Terraform must plan to detach an existing primary; lifecycle must not ignore policy attachment."
  }
  assert {
    condition     = length(aws_cloudfront_distribution.staging_cloudfront_distribution) == 1 && length(aws_cloudfront_continuous_deployment_policy.continuous_deployment_policy) == 1 && length(aws_wafv2_web_acl.waf_web_acl) == 1 && aws_cloudfront_distribution.this.web_acl_id == aws_wafv2_web_acl.waf_web_acl[0].arn
    error_message = "Detachment must retain staging, the policy, and dedicated WAF protection."
  }
}

run "seed_detached_primary" {
  command = apply
  variables {
    attach_continuous_deployment_policy = false
  }
}

run "reattach_existing_primary" {
  command = plan
  assert {
    condition     = aws_cloudfront_distribution.this.continuous_deployment_policy_id == aws_cloudfront_continuous_deployment_policy.continuous_deployment_policy[0].id
    error_message = "Terraform must plan to reattach the policy to the existing primary."
  }
}
