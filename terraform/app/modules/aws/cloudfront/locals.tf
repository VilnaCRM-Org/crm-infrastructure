locals {
  use_shared_waf       = var.enable_waf && var.shared_waf_web_acl_name != null
  create_dedicated_waf = var.enable_waf && (var.shared_waf_web_acl_name == null || var.retain_dedicated_waf)
  waf_web_acl_arn      = !var.enable_waf ? null : (local.use_shared_waf ? data.aws_wafv2_web_acl.shared[0].arn : aws_wafv2_web_acl.waf_web_acl[0].arn)
  waf_web_acl_name     = !var.enable_waf ? null : (local.use_shared_waf ? data.aws_wafv2_web_acl.shared[0].name : aws_wafv2_web_acl.waf_web_acl[0].name)

  s3_origin_id          = "${var.domain_name}-orgin-id"
  s3_failover_origin_id = "${var.domain_name}-failover-orgin-id"
  account_id            = data.aws_caller_identity.current.account_id

  waf_rules = {
    common_rule               = "AWS-AWSManagedRulesCommonRuleSet"
    amazon_ip_reputation_rule = "AWS-AWSManagedRulesAmazonIpReputationList"
    bad_inputs_rule           = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    rate_limit_rule           = "AWS-RateLimitRuleSet"
  }

  cloudwatch_alarm_source_arns = concat(
    aws_cloudwatch_metric_alarm.cloudfront_500_errors[*].arn,
    aws_cloudwatch_metric_alarm.cloudfront_origin_latency[*].arn,
    aws_cloudwatch_metric_alarm.cloudfront_staging_500_errors[*].arn,
    aws_cloudwatch_metric_alarm.cloudfront_staging_origin_latency[*].arn,
    aws_cloudwatch_metric_alarm.cloudfront_requests_anomaly_detection[*].arn,
    aws_cloudwatch_metric_alarm.wafv2_allowed_requests_anomaly_detection[*].arn,
    aws_cloudwatch_metric_alarm.wafv2_blocked_requests_anomaly_detection[*].arn,
    aws_cloudwatch_metric_alarm.wafv2_country_blocked_requests[*].arn,
    aws_cloudwatch_metric_alarm.cloudfront_requests_flood_alarm[*].arn,
    aws_cloudwatch_metric_alarm.wafv2_high_rate_blocked_requests[*].arn,
    aws_cloudwatch_metric_alarm.wafv2_scanning_alarm[*].arn,
    aws_cloudwatch_metric_alarm.wafv2_bots_alarm[*].arn,
  )
}
