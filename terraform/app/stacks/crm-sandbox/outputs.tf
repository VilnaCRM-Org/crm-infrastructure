output "sandbox_bucket_id" {
  description = "The name of the sandbox-crm S3 bucket"
  value       = module.sandbox_bucket.id
}

output "sandbox_bucket_arn" {
  description = "The ARN of the sandbox-crm S3 bucket"
  value       = module.sandbox_bucket.arn
}
