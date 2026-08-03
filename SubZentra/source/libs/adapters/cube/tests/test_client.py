from zentra_adapter_cube import CubeClient


def test_cube_client_normalizes_base_url() -> None:
    client = CubeClient("http://localhost:4000/")

    assert client._base_url == "http://localhost:4000"  # noqa: SLF001
