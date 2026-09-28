terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Pinned exactly, not "~> 6.0". No .terraform.lock.hcl is committed, so a
      # range lets `tofu init` resolve the newest 6.x — which means the plan
      # reviewed on a PR need not be the plan the merge applies. On an adoption
      # apply that is the difference between "adopt" and "replace", because a
      # provider minor can change a CustomizeDiff. A committed lockfile is the
      # stronger fix and wants `tofu providers lock` (openforge_catalog-0ab).
      version = "6.66.0"
    }
  }

  # The baseline's state bucket; apps write under their own prefix
  # (the deploy role's boundary denies infra/* and infra-frontend/*).
  backend "s3" {
    bucket         = "openforge-infra-tfstate-908027381953"
    key            = "openforge-catalog/production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "openforge-infra-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "openforge-catalog"
      Environment = "production"
      ManagedBy   = "opentofu"
      Repo        = "MasterworkTools/openforge-catalog"
    }
  }
}
