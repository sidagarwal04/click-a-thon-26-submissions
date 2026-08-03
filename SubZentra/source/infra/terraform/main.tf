resource "neon_project" "control_plane" {
  name      = "zentraos-${var.environment}"
  region_id = var.neon_region
}

resource "clickhouse_service" "audit" {
  name                  = "zentraos-audit-${var.environment}"
  cloud_provider        = "aws"
  region                = var.clickhouse_region
  password              = var.clickhouse_owner_password
  idle_scaling          = true
  idle_timeout_minutes  = 5
  min_replica_memory_gb = 8
  max_replica_memory_gb = 8

  ip_access = [
    {
      source      = var.clickhouse_allowed_cidr
      description = "ZentraOS API egress"
    }
  ]
}
