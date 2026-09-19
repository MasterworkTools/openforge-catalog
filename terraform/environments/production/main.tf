# openforge-catalog, production: the API Lambda behind an ALB, and the bucket the
# static frontend is synced to. Networking, the database, ECR and the deploy
# role's permissions boundary come from openforge-infra's state.

data "terraform_remote_state" "infra" {
  backend = "s3"
  config = {
    bucket = "openforge-infra-tfstate-${var.aws_account_id}"
    key    = "infra/production/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  infra = data.terraform_remote_state.infra.outputs
  name  = "openforge-catalog" # deploy-role boundary: every IAM name must start with this
}

# ─── Runtime secrets ──────────────────────────────────────────────────────────
# openforge-catalog/production/app is created once by scripts/create-app-secret.sh
# (API_TOKEN, SECRET_KEY, CLOUDFLARE_*). The database password is NOT copied here:
# the RDS-managed master secret can rotate, so the Lambda reads it at cold start
# from DB_SECRET_ARN (openforge/db/__init__.py).

data "aws_secretsmanager_secret_version" "app" {
  secret_id = "${local.name}/production/app"
}

locals {
  app_secret = jsondecode(data.aws_secretsmanager_secret_version.app.secret_string)
}

# ─── API Lambda ───────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "api_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name                 = "${local.name}-api"
  assume_role_policy   = data.aws_iam_policy_document.api_assume.json
  permissions_boundary = local.infra.deploy_permissions_boundary_arn
}

# Logs plus ENI management for the VPC attachment (superset of the basic execution role).
resource "aws_iam_role_policy_attachment" "api_vpc" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "api_db_secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.infra.db_secret_arn]
  }
}

resource "aws_iam_role_policy" "api_db_secret" {
  name   = "${local.name}-api-db-secret"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_db_secret.json
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 30
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name}-api"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = "${local.infra.ecr_repository_urls["openforge_catalog/api"]}:${var.image_tag}"
  architectures = ["x86_64"]
  memory_size   = 128 # as staging runs it (openforge_catalog-gvw: tune after Power Tuning)
  timeout       = 30

  # Each warm container holds a 4-connection pool; 50 containers is 200 sessions,
  # well under Aurora's cap, and bounds a traffic burst's Lambda bill.
  reserved_concurrent_executions = 50

  vpc_config {
    subnet_ids         = local.infra.subnet_ids
    security_group_ids = [local.infra.application_security_group_id]
  }

  environment {
    variables = {
      PGHOST                       = local.infra.db_cluster_endpoint
      DB_SECRET_ARN                = local.infra.db_secret_arn
      API_TOKEN                    = local.app_secret.API_TOKEN
      SECRET_KEY                   = local.app_secret.SECRET_KEY
      CLOUDFLARE_ENDPOINT          = local.app_secret.CLOUDFLARE_ENDPOINT
      CLOUDFLARE_ACCESS_KEY_ID     = local.app_secret.CLOUDFLARE_ACCESS_KEY_ID
      CLOUDFLARE_SECRET_ACCESS_KEY = local.app_secret.CLOUDFLARE_SECRET_ACCESS_KEY
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.api.name
  }

  depends_on = [aws_iam_role_policy_attachment.api_vpc]
}

# ─── ALB ──────────────────────────────────────────────────────────────────────
# ponytail: HTTP only. CloudFront reaches the ALB over port 80 (origin_protocol_policy
# http-only, as staging), so no listener cert is needed here. Add a 443 listener with
# the catalog's own ACM cert if the ALB is ever exposed without CloudFront in front.

resource "aws_lb" "api" {
  name               = local.name
  load_balancer_type = "application"
  internal           = false
  security_groups    = [local.infra.loadbalancers_security_group_id]
  subnets            = local.infra.subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api"
  target_type = "lambda"
}

resource "aws_lambda_permission" "alb" {
  statement_id  = "AllowALBInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "elasticloadbalancing.amazonaws.com"
  source_arn    = aws_lb_target_group.api.arn
}

resource "aws_lb_target_group_attachment" "api" {
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = aws_lambda_function.api.arn
  depends_on       = [aws_lambda_permission.alb]
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      status_code  = "404"
    }
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

# ─── Frontend bucket ──────────────────────────────────────────────────────────
# The Production workflow uploads the static export to s3://<bucket>/<git sha>/ and then
# promotes it to s3://<bucket>/current/, which is what openforge-infra-frontend's
# CloudFront serves.

resource "aws_s3_bucket" "site" {
  bucket = "production-${local.name}-website"
}

resource "aws_s3_bucket_website_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

data "aws_iam_policy_document" "site_public_read" {
  statement {
    sid       = "PublicReadGetObject"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket     = aws_s3_bucket.site.id
  policy     = data.aws_iam_policy_document.site_public_read.json
  depends_on = [aws_s3_bucket_public_access_block.site]
}
