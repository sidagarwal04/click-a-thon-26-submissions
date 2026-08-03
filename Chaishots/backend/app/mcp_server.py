from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import settings
from app.schemas.features import (
    ContextDiff,
    ContextDocument,
    InsightSummary,
    ProcessFeatureResult,
    RunSummary,
    SchemaArtifact,
)
from app.services.feature_pipeline import (
    FeaturePipeline,
    get_feature_pipeline_service,
    process_feature_pipeline,
)


def create_mcp_server(service: FeaturePipeline | None = None) -> MCPServer:
    """Create a thin MCP adapter over the shared application service."""

    server = MCPServer(
        "Atlys Analytics",
        instructions=(
            "Process feature folders and retrieve compact pipeline artifacts. "
            "Raw NDJSON rows are never returned by these tools."
        ),
    )

    def pipeline() -> FeaturePipeline:
        return service or get_feature_pipeline_service()

    @server.tool()
    def process_feature(feature_folder: str) -> ProcessFeatureResult:
        """Profile and process one safe folder under incoming_features."""

        active_service = pipeline()
        return process_feature_pipeline(feature_folder, service=active_service)

    @server.tool()
    def get_run_summary(run_id: str) -> RunSummary:
        """Return the compact status and headline results for one run."""

        return pipeline().get_run_summary(run_id)

    @server.tool()
    def get_schema(run_id: str) -> SchemaArtifact:
        """Return the generated ClickHouse schema artifact for one run."""

        return pipeline().get_schema(run_id)

    @server.tool()
    def get_context_diff(run_id: str) -> ContextDiff:
        """Return the versioned business-context delta for one run."""

        return pipeline().get_context_diff(run_id)

    @server.tool()
    def get_current_context() -> ContextDocument:
        """Return the latest accumulated semantic context document."""

        return pipeline().get_current_context()

    @server.tool()
    def get_insights(run_id: str) -> list[InsightSummary]:
        """Return bounded insight summaries for one run."""

        return pipeline().get_insights(run_id)

    return server


mcp = create_mcp_server()


def main() -> None:
    """Run stdio locally or Streamable HTTP when configured for LibreChat."""

    if settings.MCP_TRANSPORT == "stdio":
        mcp.run()
        return
    mcp.run(
        transport="streamable-http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                "127.0.0.1:*",
                "localhost:*",
                "[::1]:*",
                "mcp:*",
            ],
            allowed_origins=[
                "http://127.0.0.1:*",
                "http://localhost:*",
                "http://[::1]:*",
            ],
        ),
    )


if __name__ == "__main__":
    main()
