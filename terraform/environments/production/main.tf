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

  # api_db_secret named explicitly as well as the VPC attachment: a graph-only
  # no-op for this full apply, but staging's deploy runs a `-target`ed first stage
  # and -target walks dependencies rather than dependents, so without this edge the
  # only grant of secretsmanager:GetSecretValue is skipped. Kept here so the two
  # environments stay diffable and so copying staging's split job is safe.
  depends_on = [
    aws_iam_role_policy_attachment.api_vpc,
    aws_iam_role_policy.api_db_secret,
  ]
}

# ─── Migration Lambda ─────────────────────────────────────────────────────────
# The same image as the API with a different command, because nothing in CI can
# reach Aurora: the cluster's security group admits the application and bastion
# groups and a GitHub runner is in neither. The API Lambda is inside and already
# reads the password from DB_SECRET_ARN, so a second function from the same image
# is the cheapest way in — no extra build, nothing to keep in step.
#
# The deploy invokes it between the apply that creates it and the apply that
# promotes the API image, so the schema is ahead of the code that needs it.
# Production previously had no migration step at all and applied schema changes
# from the bastion by hand.

resource "aws_cloudwatch_log_group" "migrate" {
  name              = "/aws/lambda/${local.name}-migrate"
  retention_in_days = 30
}

resource "aws_lambda_function" "migrate" {
  function_name = "${local.name}-migrate"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = "${local.infra.ecr_repository_urls["openforge_catalog/api"]}:${var.image_tag}"
  architectures = ["x86_64"]

  # A migration is not a request: DDL on a table with data can take minutes and
  # no client is waiting on a 30 s budget. The ceiling rather than a guess, since
  # Lambda bills actual duration — and a statement that outran a smaller budget
  # would restart from zero on every retry and wedge every release at this gate.
  # Bound lock waits with SET lock_timeout, not with the function timeout.
  memory_size = 512
  timeout     = 900

  # Exactly one at a time, so two releases landing together cannot run DDL
  # concurrently. The second invoke is throttled, which fails that release
  # loudly rather than interleaving migrations.
  reserved_concurrent_executions = 1

  image_config {
    command = ["openforge.app.migrate.lambda_handler"]
  }

  # The same subnets and the same single security group as the API, which is
  # worth keeping identical: Lambda then reuses the API's Hyperplane ENIs rather
  # than creating its own, so this costs no subnet addresses and no ENI stall on
  # a first invoke.
  vpc_config {
    subnet_ids         = local.infra.subnet_ids
    security_group_ids = [local.infra.application_security_group_id]
  }

  # Only what it needs to reach the database. No Cloudflare credentials and no
  # API_TOKEN: this function answers to nobody and writes no files.
  #
  # No PGCONNECT_TIMEOUT, which is the one deliberate difference from staging.
  # There it is set to 120 because that cluster runs at min_capacity 0 with a
  # one-hour auto-pause and a resume takes about 20 s. This cluster has a
  # min_capacity of 0.5 and no auto-pause configured, so there is no resume to
  # wait for and psycopg's own 130 s default is the bound.
  environment {
    variables = {
      PGHOST        = local.infra.db_cluster_endpoint
      DB_SECRET_ARN = local.infra.db_secret_arn
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.migrate.name
  }

  # api_db_secret named explicitly, not just implied. The first apply is
  # `-target`ed at this function, and -target walks dependencies rather than
  # dependents: this policy is attached *to* aws_iam_role.api rather than
  # referenced *by* it, so without this edge a change to the only grant of
  # secretsmanager:GetSecretValue would be skipped by the apply that runs before
  # the invoke — and the invoke would fail to read its password for a reason
  # nothing in the plan mentioned.
  depends_on = [
    aws_iam_role_policy_attachment.api_vpc,
    aws_iam_role_policy.api_db_secret,
  ]
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
