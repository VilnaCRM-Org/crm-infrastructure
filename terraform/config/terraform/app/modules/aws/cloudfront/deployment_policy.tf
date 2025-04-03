resource "aws_cloudfront_continuous_deployment_policy" "crm_continuous_deployment_policy" {
  enabled = true

  staging_distribution_dns_names {
    items    = [aws_cloudfront_distribution.staging.domain_name]
    quantity = 1
  }

  traffic_config {
    type = "SingleWeight"
    single_weight_config {
      weight = "0.15"
    }
  }
}