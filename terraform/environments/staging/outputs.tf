# Consumed by the Staging workflow (which function to invoke, which bucket to sync)
# and by whoever is pointing CloudFront at the ALB.

output "api_alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "site_website_endpoint" {
  value = aws_s3_bucket_website_configuration.site.website_endpoint
}

output "api_function_name" {
  value = aws_lambda_function.api.function_name
}

output "migrate_function_name" {
  value = aws_lambda_function.migrate.function_name
}
