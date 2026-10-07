# openforge-catalog, staging: the API Lambda behind an ALB, the migration Lambda the
# deploy invokes, and the bucket the static frontend is synced to. Networking, the
# database, ECR and the deploy role's permissions boundary come from openforge-infra.
#
# Deliberately kept diffable against ../production: the two files should differ only
# in account, environment name, bucket prefix, and the migration function — which
# lives here first because staging is where a new deploy step ought to be proven
# (openforge_catalog-jag).
#
# Staging predates tofu, so most of this is adopting what is already running. See
# imports.tf for what is adopted, and for the one adopted attribute that does not
# match live (the ALB's subnet set, widened on purpose).

data "terraform_remote_state" "infra" {
  backend = "s3"
  config = {
    bucket = "openforge-infra-tfstate-${var.aws_account_id}"
    key    = "infra/staging/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  infra = data.terraform_remote_state.infra.outputs
  name  = "openforge-catalog" # deploy-role boundary: every IAM name must start with this
}

# ─── Runtime secrets ──────────────────────────────────────────────────────────
# openforge-catalog/staging/app is created once by scripts/create-app-secret.sh
# (API_TOKEN, SECRET_KEY, CLOUDFLARE_*). The database password is NOT copied here:
# the RDS-managed master secret can rotate, so the Lambda reads it at cold start
# from DB_SECRET_ARN (openforge/db/__init__.py).
#
# The hand-built function this replaces carried a literal PGPASSWORD instead. That
# is the thing to keep out of the replacement: the value happened to still be
# current, but nothing would have told anyone the day it stopped being.

data "aws_secretsmanager_secret_version" "app" {
  secret_id = "${local.name}/staging/app"
}

locals {
  app_secret = jsondecode(data.aws_secretsmanager_secret_version.app.secret_string)
}

# ─── Lambda IAM ───────────────────────────────────────────────────────────────
# One role for all three functions: they need exactly the same two things — ENI
# management for the VPC attachment and the database secret. A separate role
# would differ only in name.
#
# Worth knowing rather than changing: this is also the internet-facing API's
# identity, so a grant added here for a background function is a grant the API
# gains too.

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

# ─── API Lambda ───────────────────────────────────────────────────────────────

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
  memory_size   = 128 # openforge_catalog-gvw: tune after Power Tuning
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

  depends_on = [
    aws_iam_role_policy_attachment.api_vpc,
    aws_iam_role_policy.api_db_secret,
  ]
}

# ─── Migration Lambda ─────────────────────────────────────────────────────────
# The same image with a different command. Aurora only accepts connections from
# inside the VPC — its security group admits the application and bastion groups
# and nothing else — and a GitHub runner is outside it, which is why migrations
# were manual. This function is inside, so it is the way in.
#
# (Not because the subnets are private: staging is the default VPC and all six
# subnets are MapPublicIpOnLaunch. The security group is what closes the door.)
#
# The deploy invokes it between the apply that creates it and the apply that
# promotes the API image, so the schema is ahead of the code that needs it.

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

  # A migration is not a request: DDL on a table with data can take minutes, and
  # there is no client waiting on a 30 s budget. The ceiling rather than a guess —
  # Lambda bills actual duration, so a larger budget costs nothing, and a statement
  # that outran a smaller one would restart from zero on every retry and wedge
  # every merge to test at this gate. Bound lock waits with SET lock_timeout, not
  # with the function timeout, which migrate.py does per version.
  memory_size = 512
  timeout     = 900

  # Exactly one at a time. Two deploys landing together would otherwise run DDL
  # concurrently; the second invoke is throttled instead, which fails that
  # deploy loudly rather than interleaving migrations.
  reserved_concurrent_executions = 1

  image_config {
    command = ["openforge.app.migrate.lambda_handler"]
  }

  vpc_config {
    subnet_ids         = local.infra.subnet_ids
    security_group_ids = [local.infra.application_security_group_id]
  }

  # Only what it needs to reach the database. No Cloudflare credentials and no
  # API_TOKEN: this function answers to nobody and writes no files.
  # libpq reads PGCONNECT_TIMEOUT itself, so this needs no code change.
  #
  # Not because the alternative is waiting forever — that was this comment's first
  # version and it was wrong. psycopg substitutes its own 130 s default when
  # connect_timeout is absent or <= 0 (conninfo.py), so libpq's 0 never applies and
  # the pre-existing bound was already 130 s, comfortably inside this function's 900.
  #
  # What 120 buys is a bound matched to the *measured* normal case: staging Aurora
  # runs at min_capacity 0 with a one-hour auto-pause, and a resume from zero takes
  # about 20 s. 120 is ~6x that, and each of the ~21 sequential connects gets its own
  # budget inside 900 s. Only this function sets it: use_pool=False means
  # psycopg.connect raises ConnectionTimeout straight out of the handler, whereas the
  # API's pool catches it, logs a warning and reschedules — so there the value would
  # never reach a caller, would burn aborted attempts on every idle cold start, and
  # would diverge from production for nothing.
  environment {
    variables = {
      PGHOST            = local.infra.db_cluster_endpoint
      DB_SECRET_ARN     = local.infra.db_secret_arn
      PGCONNECT_TIMEOUT = 120
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.migrate.name
  }

  # api_db_secret is named explicitly, not just implied. The deploy's first apply
  # is `-target`ed at this function, and -target walks dependencies rather than
  # dependents: this policy is attached *to* aws_iam_role.api rather than
  # referenced *by* it, so without this edge a change to the only grant of
  # secretsmanager:GetSecretValue would be skipped by the one apply that runs
  # before the migration is invoked — and the invoke would fail to read its
  # password for a reason nothing in the plan mentioned.
  depends_on = [
    aws_iam_role_policy_attachment.api_vpc,
    aws_iam_role_policy.api_db_secret,
  ]
}

# The fixtures a release carries, loaded the same way its migrations are: a
# function from the same image, invoked between the schema and the API image.
# Data had been manual in both environments, and a release whose content is a
# fixture shipped nothing until someone ran bin/fixtures on the bastion
# (openforge_catalog-25m).
#
# No upload: Dockerfile.api.deploy copies the whole openforge package, so the
# fixtures are already on this function's filesystem.

resource "aws_cloudwatch_log_group" "fixtures" {
  name              = "/aws/lambda/${local.name}-fixtures"
  retention_in_days = 30
}

resource "aws_lambda_function" "fixtures" {
  function_name = "${local.name}-fixtures"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = "${local.infra.ecr_repository_urls["openforge_catalog/api"]}:${var.image_tag}"
  architectures = ["x86_64"]

  # Not for the memory: a measured full load of the real catalog peaks at
  # ~231 MiB, so 512 would hold it. This is for the CPU, because the load is
  # 81% CPU-bound and at 512 MB (~0.29 vCPU) its ~183 s of CPU becomes ~630 s
  # against the 900 s ceiling.
  #
  # Note where that argument stops: Lambda scales CPU with memory only up to
  # 1769 MB, which is one full vCPU, and this handler is single-threaded
  # Python. So 2048 buys nothing over 1769 — it is 16% of fractions of a cent
  # per deploy, kept for the round number, and not a reason to go higher.
  #
  # TIME is the one to watch. A measured no-op load of all 45 fixtures is
  # ~175 s against this 900 s ceiling, and it grows with files x catalog size:
  # _load_existing_blueprints is uncached and the loader builds one per
  # blueprint fixture file. There is headroom now; a catalog several times
  # this size would not have it.
  #
  # openforge_catalog-nhf is the 128 MB API Lambda being asked to do this
  # work. A dedicated function is the fix for that, so it should not inherit
  # the ceiling.
  memory_size = 2048
  timeout     = 900

  # One at a time. Two deploys landing together would interleave loads of the
  # same tables; the second invoke is throttled instead, which fails that
  # deploy loudly.
  reserved_concurrent_executions = 1

  image_config {
    command = ["openforge.app.load_fixtures.lambda_handler"]
  }

  vpc_config {
    subnet_ids         = local.infra.subnet_ids
    security_group_ids = [local.infra.application_security_group_id]
  }

  # Only what it needs to reach the database — no Cloudflare credentials and
  # no API_TOKEN. PGCONNECT_TIMEOUT for the same reason the migration sets it:
  # Aurora resumes from min_capacity 0 and a resume from zero takes ~20 s, so
  # each of this function's connects gets a budget matched to the measured
  # normal case rather than psycopg's 130 s default.
  environment {
    variables = {
      PGHOST            = local.infra.db_cluster_endpoint
      DB_SECRET_ARN     = local.infra.db_secret_arn
      PGCONNECT_TIMEOUT = 120
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.fixtures.name
  }

  # Named for the same reason as the migration's: the deploy's first apply is
  # -target'ed at these functions, and -target walks dependencies rather than
  # dependents, so without this edge a change to the only grant of
  # secretsmanager:GetSecretValue would be skipped by the apply that runs
  # before this is invoked.
  depends_on = [
    aws_iam_role_policy_attachment.api_vpc,
    aws_iam_role_policy.api_db_secret,
  ]
}

# ─── ALB ──────────────────────────────────────────────────────────────────────
# ponytail: HTTP only. CloudFront reaches the ALB over port 80 (origin_protocol_policy
# http-only), so no listener cert is needed here. The ALB this adopts also carries a
# port 443 listener that nothing uses; it is left out of tofu on purpose and removed
# by hand (openforge_catalog-rc2) rather than modelled.

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
# The Staging workflow uploads the static export to s3://<bucket>/<git sha>/ and then
# promotes it to s3://<bucket>/current/, which is what CloudFront serves.

resource "aws_s3_bucket" "site" {
  bucket = "staging-${local.name}-website"
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
