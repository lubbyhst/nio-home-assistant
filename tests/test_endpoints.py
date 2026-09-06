"""Tests for the documented NIO service endpoints."""

import unittest

from _load import load_module

const = load_module("const")


class TestNioEndpoints(unittest.TestCase):
    def test_authorization_uses_portal_host(self) -> None:
        """Browser authorization and API calls use their documented hosts."""
        self.assertEqual(
            f"{const.OAUTH_BASE_URL}{const.AUTHORIZE_PATH}",
            "https://open-eu.nio.com/oauth2/authorize",
        )
        self.assertEqual(
            f"{const.OAUTH_BASE_URL}{const.TOKEN_PATH}",
            "https://open-eu.nio.com/api/2/oauth/token",
        )
        self.assertEqual(const.API_BASE_URL, "https://open-api-eu.nio.com")

    def test_all_read_only_telemetry_scopes_are_requested(self) -> None:
        self.assertEqual(
            set(const.OAUTH_SCOPES),
            {
                "vehicle:connectivity:read",
                "vehicle:body:read",
                "vehicle:dynamics:read",
                "vehicle:location:read",
                "vehicle:energy:read",
                "vehicle:cabin:read",
                "vehicle:powertrain:read",
                "vehicle:diagnostics:read",
                "aftersales:read",
            },
        )
