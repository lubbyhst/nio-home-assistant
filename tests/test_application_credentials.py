"""Application-credential tests for NIO Open Telematics."""

from homeassistant.core import HomeAssistant

from custom_components.nio_telematics.application_credentials import (
    NioOAuth2Implementation,
)


def test_authorize_request_uses_nios_default_scope_set(
    hass: HomeAssistant,
) -> None:
    """Omitting scope lets NIO grant every permission allowed for the app."""
    implementation = NioOAuth2Implementation(
        hass,
        "nio-local",
        "client-id",
        authorize_url="https://open-eu.nio.com/oauth2/authorize",
        token_url="https://open-eu.nio.com/api/2/oauth/token",
        client_secret="client-secret",
    )

    assert "scope" not in implementation.extra_authorize_data
    assert implementation.extra_authorize_data["code_challenge_method"] == "S256"
