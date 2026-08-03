output "neon_project_id" {
  description = "Neon control-plane project identifier."
  value       = neon_project.control_plane.id
}

output "neon_owner_connection_uri" {
  description = "Migration-owner connection URI. Store in the deployment secret manager."
  value       = neon_project.control_plane.connection_uri
  sensitive   = true
}

output "clickhouse_service_id" {
  description = "ClickHouse audit service identifier."
  value       = clickhouse_service.audit.id
}

output "clickhouse_endpoints" {
  description = "ClickHouse service endpoints."
  value       = clickhouse_service.audit.endpoints
}
