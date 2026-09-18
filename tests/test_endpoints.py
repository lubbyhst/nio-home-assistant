"""Tests for the documented NIO service endpoints."""

import unittest

from _load import load_module

const = load_module("const")


class TestNioEndpoints(unittest.TestCase):
    def test_supported_endpoint_inventory_excludes_non_telemetry_apis(self) -> None:
        self.assertEqual(
            const.SUPPORTED_ENDPOINTS,
            (
                "door_status",
                "fridge_status",
                "light_status",
                "window_status",
                "driving_data",
                "vehicle_status_changes",
                "vehicle_status",
                "position_status",
                "trip_status",
                "cell_status",
                "extremum_data",
                "soc_status",
                "heating_status",
                "hvac_status",
                "driving_motor",
                "alarm_signal",
                "odometer_report",
            ),
        )

    def test_diagnostic_sensors_match_supported_endpoint_inventory(self) -> None:
        from custom_components.nio_telematics.sensor import SENSORS

        diagnostic_keys = {
            description.key
            for description in SENSORS
            if description.key.startswith("api_")
            and description.key != "api_availability"
        }

        self.assertEqual(
            diagnostic_keys,
            {f"api_{endpoint}" for endpoint in const.SUPPORTED_ENDPOINTS},
        )

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

    def test_scope_policy_revision_uses_provider_default(self) -> None:
        """Changing to NIO's full-permission default triggers reauthorization."""
        self.assertEqual(const.OAUTH_SCOPE_REVISION, 2)
