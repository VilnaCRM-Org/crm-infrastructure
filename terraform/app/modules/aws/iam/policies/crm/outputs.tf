output "policy_arns" {
  value = {
    crm_infra_lambda_policy     = { arn = "${aws_iam_policy.lambda_policy.arn}" },
    crm_infra_dns_policy        = { arn = "${aws_iam_policy.dns_policy.arn}" }
    crm_infra_cloudfront_policy = { arn = "${aws_iam_policy.cloudfront_policy.arn}" }
    crm_infra_general_policy    = { arn = "${aws_iam_policy.general_policy.arn}" }
    crm_infra_iam_policy        = { arn = "${aws_iam_policy.iam_policy.arn}" }
    crm_infra_sns_policy        = { arn = "${aws_iam_policy.sns_policy.arn}" }
    crm_infra_s3_policy         = { arn = "${aws_iam_policy.s3_policy.arn}" }
  }
  description = "ARNs of policies"
}