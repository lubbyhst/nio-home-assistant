"""Application-credential regression tests for NIO Open Telematics."""

from pathlib import Path

import pytest


def test_authorize_request_uses_nios_default_scope_set() -> None:
    """The implementation must not override PKCE data with a scope parameter."""
    source = (
        Path(__file__).parents[1]
        / "custom_components"
        / "nio_telematics"
        / "application_credentials.py"
    ).read_text(encoding="utf-8")

    assert "OAUTH_SCOPES" not in source
    assert '"scope"' not in source
    assert "'scope'" not in source


@pytest.mark.parametrize("placeholder", ("console_url", "redirect_url"))
def test_application_credential_description_placeholder_is_defined(
    placeholder: str,
) -> None:
    """Every URL placeholder used by the credential description is defined."""
    source = (
        Path(__file__).parents[1]
        / "custom_components"
        / "nio_telematics"
        / "application_credentials.py"
    ).read_text(encoding="utf-8")

    assert f'"{placeholder}"' in source
