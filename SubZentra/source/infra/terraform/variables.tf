variable "environment" {
  description = "Environment suffix used in managed resource names."
  type        = string
  default     = "development"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production."
  }
}

variable "neon_region" {
  description = "Neon US East region identifier."
  type        = string
  default     = "aws-us-east-2"
}

variable "clickhouse_region" {
  description = "ClickHouse Cloud US East region identifier."
  type        = string
  default     = "us-east-1"
}

variable "clickhouse_allowed_cidr" {
  description = "CIDR permitted to connect to the audit service. Never use 0.0.0.0/0 outside short-lived development."
  type        = string
}

variable "clickhouse_owner_password" {
  description = "Initial ClickHouse service owner password."
  type        = string
  sensitive   = true
}

variable "aws_region" {
  description = "AWS region hosting the Sequence Step execution Lambda."
  type        = string
  default     = "us-east-1"
}

variable "sequence_execution_image_uri" {
  description = "ECR image URI for the Sequence Step execution Lambda (libs/adapters/sequence-execution/Dockerfile), tagged and pushed by CI before apply."
  type        = string
}

variable "connector_clickhouse_host" {
  description = "Host of the ClickHouse instance Connector-sourced Sequence Steps read from."
  type        = string
}

variable "database_runtime_url" {
  description = "Runtime-role Postgres connection string the Lambda uses to resolve a Sequence's Raw Table reference."
  type        = string
  sensitive   = true
}
