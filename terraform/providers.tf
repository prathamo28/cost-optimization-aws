terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Values supplied via backend config or -backend-config flag
    # terraform init -backend-config="bucket=my-tfstate" \
    #                -backend-config="key=cost-optimization/terraform.tfstate" \
    #                -backend-config="region=eu-west-1"
    bucket         = "REPLACE_WITH_YOUR_STATE_BUCKET"
    key            = "cost-optimization/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      "cost:managed" = "terraform"
      "cost:repo"    = "cost-optimization-aws"
    }
  }
}
