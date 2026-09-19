resource "aws_cloudwatch_log_group" "waf_web_acl_log_group" {
  # Preserve the historical 60-day audit trail after migrating to shared WAF.
  # Cleanup of the empty group can follow once the retention period has elapsed.
  count = var.enable_waf ? 1 : 0
  #checkov:skip=CKV_AWS_338: The one year is too much
  #checkov:skip=CKV_AWS_158: KMS encryption is not needed
  provider          = aws.us-east-1
  name              = "aws-waf-logs-wafv2-web-acl-crm-crm"
  retention_in_days = 60

}
