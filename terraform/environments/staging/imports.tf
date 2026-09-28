# Staging was built by hand before this repo had tofu, so these resources already
# exist and are adopted rather than created. Safe to delete after the first apply
# has recorded them in state.
#
# ─── ONE MANUAL STEP BEFORE THE FIRST APPLY ───────────────────────────────────
#
# The target group below still has the OLD function registered:
#
#   arn:aws:lambda:us-east-1:682033461796:function:Openforge-Catalog-API
#
# A Lambda target group holds exactly one target, and aws_lb_target_group_attachment
# has no import, so the apply cannot swap it — it would try to register the new
# function into a full target group and fail. Deregister the old one first:
#
#   aws lambda remove-permission --profile staging \
#     --function-name Openforge-Catalog-API --statement-id AllowALBInvoke || true
#   aws elbv2 deregister-targets --profile staging \
#     --target-group-arn arn:aws:elasticloadbalancing:us-east-1:682033461796:targetgroup/openforge-catalog-api/cd223d56e9899b78 \
#     --targets Id=arn:aws:lambda:us-east-1:682033461796:function:Openforge-Catalog-API
#
# Staging's /api/* is down from that command until the apply finishes. That is the
# whole outage, it is staging, and the old function stays in place as the rollback
# until openforge_catalog-rc2 removes it.
#
# ─── What is NOT imported, and why ────────────────────────────────────────────
#
# The function and its role: they are named Openforge-Catalog-API and
# Openforge-Catalog-API-role-ogdz6ix0 (service-role path). function_name is
# ForceNew, and the deploy role may only touch IAM named openforge-catalog-*, so
# neither can become the production-shaped resource. Tofu creates
# openforge-catalog-api fresh; the old pair is deleted by hand afterwards.
#
# The port 443 listener on the ALB: unused, CloudFront is http-only on port 80.

import {
  to = aws_lb.api
  id = "arn:aws:elasticloadbalancing:us-east-1:682033461796:loadbalancer/app/openforge-catalog/67abed33a99d7bf7"
}

import {
  to = aws_lb_target_group.api
  id = "arn:aws:elasticloadbalancing:us-east-1:682033461796:targetgroup/openforge-catalog-api/cd223d56e9899b78"
}

import {
  to = aws_lb_listener.http
  id = "arn:aws:elasticloadbalancing:us-east-1:682033461796:listener/app/openforge-catalog/67abed33a99d7bf7/55666e4452ada2aa"
}

import {
  to = aws_lb_listener_rule.api
  id = "arn:aws:elasticloadbalancing:us-east-1:682033461796:listener-rule/app/openforge-catalog/67abed33a99d7bf7/55666e4452ada2aa/5f58e2674418a9f6"
}

import {
  to = aws_s3_bucket.site
  id = "staging-openforge-catalog-website"
}

import {
  to = aws_s3_bucket_website_configuration.site
  id = "staging-openforge-catalog-website"
}

import {
  to = aws_s3_bucket_public_access_block.site
  id = "staging-openforge-catalog-website"
}

import {
  to = aws_s3_bucket_policy.site
  id = "staging-openforge-catalog-website"
}
