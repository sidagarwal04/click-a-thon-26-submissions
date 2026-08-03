# Sequence Step execution — the first AWS compute resource in this repo.
# Everything else Terraform manages here (Neon, ClickHouse Cloud) is SaaS
# provisioning, not first-party AWS infrastructure. See
# docs/adr/0022-sequence-step-execution-is-distinct-from-phase-3-query-execution.md
# for why this exists alongside, not instead of, the DuckDB/Cloud Run
# execution engine ADR-0012 already accepted for governed queries.

resource "aws_ecr_repository" "sequence_execution" {
  name                 = "zentraos-sequence-execution-${var.environment}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

data "aws_iam_policy_document" "sequence_execution_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sequence_execution" {
  name               = "zentraos-sequence-execution-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.sequence_execution_assume_role.json
}

# Logs only: the handler reaches Postgres and ClickHouse over the network
# (their own credentials gate that access), not through an AWS-IAM-gated
# service — so no broader action is needed here.
data "aws_iam_policy_document" "sequence_execution_logs" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/*"]
  }
}

resource "aws_iam_role_policy" "sequence_execution_logs" {
  name   = "logs"
  role   = aws_iam_role.sequence_execution.id
  policy = data.aws_iam_policy_document.sequence_execution_logs.json
}

resource "aws_lambda_function" "sequence_execution" {
  function_name = "zentraos-sequence-execution-${var.environment}"
  role          = aws_iam_role.sequence_execution.arn
  package_type  = "Image"
  image_uri     = var.sequence_execution_image_uri

  # Sized for chDB's in-memory execution over the small, bounded row sets a
  # single typed operation produces; revisit if larger fixtures are observed.
  memory_size = 3008
  timeout     = 60

  environment {
    variables = {
      DATABASE_RUNTIME_URL      = var.database_runtime_url
      CONNECTOR_CLICKHOUSE_HOST = var.connector_clickhouse_host
      SEQUENCE_STORAGE_ROOT     = "/tmp/sequence-execution"
    }
  }
}

output "sequence_execution_function_name" {
  value = aws_lambda_function.sequence_execution.function_name
}

output "sequence_execution_function_arn" {
  value = aws_lambda_function.sequence_execution.arn
}

output "sequence_execution_ecr_repository_url" {
  value = aws_ecr_repository.sequence_execution.repository_url
}
