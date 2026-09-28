# Staging was built by hand before this repo had tofu, so these resources already
# exist and are adopted rather than created. Safe to delete after the first apply
# has recorded them in state.
#
# ─── There is no manual step ───────────────────────────────────────────────────
#
# An earlier version of this file told you to deregister the old function from the
# target group first, because a Lambda target group holds exactly one target and
# `aws_lb_target_group_attachment` could not be imported. The first half is true;
# the second stopped being true at provider v6.40.0, which documents a
# comma-separated `target_group_arn,target_id` import. `~> 6.0` resolves well past
# that, so the attachment is imported below and `target_id` — which is ForceNew —
# makes the apply deregister the old function and register the new one itself, in
# milliseconds.
#
# That instruction was worse than redundant. It took `/api/*` down *before* an
# apply that cannot currently succeed (the app secret is read as a data source and
# is resolved at plan time, so a missing one fails the plan having changed
# nothing), leaving staging broken with recovery by hand. It also told you to
# remove a `AllowALBInvoke` statement that does not exist — the live statement id
# is `AWS-ALB_Invoke-targetgroup-openforge-catalog-api-cd223d56e9899b78`, so the
# command only ever raised into a `|| true`. Had it worked it would have broken the
# rollback it was meant to preserve, because re-registering the old function needs
# that permission.
#
# ─── The first apply widens the ALB ────────────────────────────────────────────
#
# One adopted attribute does not match live, deliberately. The ALB spans 2 subnets
# today; `main.tf` declares `local.infra.subnet_ids`, which is all six default-VPC
# subnets, because that is the expression production uses and this environment is
# meant to be diffable against it. `subnets` is not ForceNew on an ALB — the
# provider's `ForceNew(subnets)` only applies to network load balancers — so this
# is an in-place `SetSubnets` that adds four AZs and detaches nothing. The DNS name
# is unchanged, so CloudFront's origin is unaffected.
#
# ─── What is NOT imported, and why ────────────────────────────────────────────
#
# The function and its role: they are named Openforge-Catalog-API and
# Openforge-Catalog-API-role-ogdz6ix0 (service-role path). function_name is
# ForceNew, and the deploy role may only touch IAM named openforge-catalog-*, so
# neither can become the production-shaped resource. Tofu creates
# openforge-catalog-api fresh; the old pair is deleted by hand once staging serves
# from the new one (openforge_catalog-rc2), and until then it is the rollback.
#
# The port 443 listener: unused, and CloudFront reaches the ALB http-only on port
# 80. Tofu cannot prune a listener it does not model, so leaving it out is safe.
# Note it forwards to the target group below, so after this apply that listener
# invokes the new function too.

import {
  to = aws_lb.api
  id = "arn:aws:elasticloadbalancing:us-east-1:682033461796:loadbalancer/app/openforge-catalog/67abed33a99d7bf7"
}

import {
  to = aws_lb_target_group.api
  id = "arn:aws:elasticloadbalancing:us-east-1:682033461796:targetgroup/openforge-catalog-api/cd223d56e9899b78"
}

# The old function, so the apply swaps it for the new one rather than trying to add
# a second target to a group that can only hold one.
import {
  to = aws_lb_target_group_attachment.api
  id = "arn:aws:elasticloadbalancing:us-east-1:682033461796:targetgroup/openforge-catalog-api/cd223d56e9899b78,arn:aws:lambda:us-east-1:682033461796:function:Openforge-Catalog-API"
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
