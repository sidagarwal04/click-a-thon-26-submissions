import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.app import create_app

def test_document_endpoints():
    app = create_app()
    client = TestClient(app)

    # 1. Test metadata of a valid file (base_context.md)
    response = client.get("/api/documents/metadata?path=base_context.md")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["name"] == "base_context.md"
    assert "size" in data
    assert data["extension"] == ".md"

    # 2. Test metadata of a non-existent file
    response = client.get("/api/documents/metadata?path=non_existent_file.txt")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False

    # 3. Test content retrieval
    response = client.get("/api/documents/content?path=base_context.md")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "base_context.md"
    assert "content" in data
    assert "# Atlys Business Context" in data["content"] or "Atlys" in data["content"]

    # 4. Test download retrieval
    response = client.get("/api/documents/download?path=base_context.md")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert "attachment" in response.headers["content-disposition"]
    assert "base_context.md" in response.headers["content-disposition"]

    # 5. Security: Path traversal attempts
    response = client.get("/api/documents/metadata?path=../../.env")
    assert response.status_code == 403

    response = client.get("/api/documents/content?path=../.env")
    assert response.status_code == 403

    response = client.get("/api/documents/download?path=../../etc/passwd")
    assert response.status_code == 403


def test_save_document_tool():
    from service.mcp_server import AtlysMcpServer
    from unittest.mock import PropertyMock, patch
    import shutil
    
    app = create_app()
    state = app.state
    test_gen_dir = Path(state.settings.atlys_root) / "generated_test"
    
    with patch("service.settings.Settings.generated_dir", new_callable=PropertyMock) as mock_gen:
        mock_gen.return_value = test_gen_dir
        
        # Initialize MCP Server
        mcp = AtlysMcpServer(
            bus=state.bus,
            instrumentation=state.instrumentation,
            context=state.context,
            analytics=state.analytics,
            store=state.store,
            settings=state.settings
        )
        
        # Test saving a document
        res = mcp._save_document(
            filename="test_report.md",
            content="## Test Report\nContent goes here.",
            subdirectory="reports"
        )
        assert res.get("success") is True
        assert "generated_test/reports/test_report.md" in res.get("path")
        
        # Verify we can read it via FastAPI
        client = TestClient(app)
        response = client.get(f"/api/documents/content?path={res.get('path')}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_report.md"
        assert "Test Report" in data["content"]
        
    # Clean up the test directory
    if test_gen_dir.exists():
        shutil.rmtree(test_gen_dir)


