locals {
  s3_origin_id          = "${var.project_name}-${var.domain_name}-origin-id"
  s3_failover_origin_id = "${var.project_name}-${var.domain_name}-failover-origin-id"
  account_id            = data.aws_caller_identity.current.account_id

  waf_rules = {
    common_rule               = "AWS-AWSManagedRulesCommonRuleSet"
    amazon_ip_reputation_rule = "AWS-AWSManagedRulesAmazonIpReputationList"
    bad_inputs_rule           = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    rate_limit_rule           = "AWS-RateLimitRuleSet"
  }
}