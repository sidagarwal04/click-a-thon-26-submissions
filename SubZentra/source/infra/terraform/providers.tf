provider "clickhouse" {}

provider "neon" {}

provider "aws" {
  region = var.aws_region
}
