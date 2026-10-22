# A sketch of the ECS Fargate shape. It is validated in CI and never applied.
terraform {
  required_version = ">= 1.10"

  # Partial config: the bucket, key and region come from `-backend-config=backend.hcl`.
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.region
}
