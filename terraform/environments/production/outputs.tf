# Consumed by openforge-infra-frontend (CloudFront origins).

output "api_alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "site_website_endpoint" {
  value = aws_s3_bucket_website_configuration.site.website_endpoint
}

output "api_function_name" {
  value = aws_lambda_function.api.function_name
}

# Not what the deploy reads: the apply before the invoke is -target'ed, so its
# outputs are not guaranteed refreshed and the workflow uses the fixed name.
# Here so the two environments stay diffable.
output "migrate_function_name" {
  value = aws_lambda_function.migrate.function_name
}
