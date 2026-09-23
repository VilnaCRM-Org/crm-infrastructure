resource "aws_cloudfront_function" "routing_function" {
  provider = aws.us-east-1
  name     = "crm-routing-function"
  runtime  = "cloudfront-js-2.0"
  comment  = "Serve the CRM SPA shell for extensionless navigation"
  publish  = true
  code     = file("${path.module}/routing.js")
}
