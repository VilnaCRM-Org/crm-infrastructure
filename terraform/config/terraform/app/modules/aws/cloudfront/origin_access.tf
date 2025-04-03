resource "aws_cloudfront_origin_access_control" "this" {
  name                              = "${var.project_name}-${var.domain_name}"
  description                       = "${var.project_name}-${var.domain_name} OAC"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_origin_access_control" "replication" {
  name                              = "${var.project_name}-${var.domain_name}-replication"
  description                       = "${var.project_name}-${var.domain_name} OAC"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}