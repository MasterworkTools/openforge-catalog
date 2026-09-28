# Consumed by whoever is pointing CloudFront at the ALB, and useful for confirming
# by hand what the deploy is talking to. The Staging workflow does NOT read
# migrate_function_name: the apply that precedes the invoke is -target'ed, so its
# outputs are not guaranteed refreshed, and the workflow uses the fixed name instead.

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
