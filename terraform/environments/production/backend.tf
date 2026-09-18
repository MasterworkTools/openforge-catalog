terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
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
