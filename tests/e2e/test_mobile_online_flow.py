import pytest


@pytest.mark.e2e
def test_mobile_online_flow_requires_running_reference_server():
    """The full browser flow is executed by the release command against a started server."""
    pytest.skip("Run with the configured Playwright reference server")
