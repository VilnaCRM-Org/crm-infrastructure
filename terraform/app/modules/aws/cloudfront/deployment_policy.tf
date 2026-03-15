resource "aws_cloudfront_continuous_deployment_policy" "continuous_deployment_policy" {
  count   = var.enable_cloudfront_staging ? 1 : 0
  enabled = true

  staging_distribution_dns_names {
    quantity = 1
    items    = [aws_cloudfront_distribution.staging_cloudfront_distribution[0].domain_name]
  }

  traffic_config {
    type = var.continuous_deployment_policy_type

    dynamic "single_weight_config" {
      for_each = var.continuous_deployment_policy_type == "SingleWeight" ? [1] : []
      content {
        weight = var.continuous_deployment_policy_weight
      }
    }

    dynamic "single_header_config" {
      for_each = var.continuous_deployment_policy_type == "SingleHeader" ? [1] : []
      content {
        header = "aws-cf-cd-${var.continuous_deployment_policy_header}"
        value  = var.continuous_deployment_policy_header
      }
    }
  }

  depends_on = [aws_cloudfront_distribution.staging_cloudfront_distribution[0]]
}
