"""Tests for the documented NIO service endpoints."""

import unittest

from _load import load_module

from custom_components.nio_telematics.api import (
    ON_DEMAND_OPERATION_IDS,
    ON_DEMAND_OPERATIONS,
    NioApiClient,
)
from custom_components.nio_telematics.coordinator import NioDataUpdateCoordinator

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

    def test_on_demand_operations_include_history_filters_and_non_polled_calls(
        self,
    ) -> None:
        """Expose filtered vehicle history and non-polled catalog operations."""
        self.assertEqual(
            set(ON_DEMAND_OPERATIONS),
            {
                "vehicle_status_history",
                "adas_snapshots",
                "adas_events",
                "extract_adas_snapshot",
                "download_adas_event",
                "nomi_asr_files",
                "vehicle_recalls",
                "recall_campaign",
            },
        )

    def test_implementation_covers_the_full_24_operation_catalog(self) -> None:
        """Keep polled feeds plus on-demand operations aligned with NIO's spec."""
        expected_change_resources = {
            "door_status",
            "fridge_status",
            "light_status",
            "window_status",
            "driving_data",
            "vehicle_status_changes",
            "position_status",
            "trip_status",
            "cell_status",
            "extremum_data",
            "soc_status",
            "heating_status",
            "hvac_status",
            "driving_motor",
            "alarm_signal",
        }
        change_operation_ids = {
            "door_status": "getDoorStatusChanges",
            "fridge_status": "getFridgeStatusChanges",
            "light_status": "getLightStatusChanges",
            "window_status": "getWindowStatusChanges",
            "driving_data": "getDrivingDataChanges",
            "vehicle_status_changes": "getVehicleStatusChanges",
            "position_status": "getPositionStatusChanges",
            "trip_status": "getTripStatusChanges",
            "cell_status": "getCellStatusChanges",
            "extremum_data": "getExtremumDataChanges",
            "soc_status": "getSOCStatusChanges",
            "heating_status": "getHeatingStatusChanges",
            "hvac_status": "getHVACStatusChanges",
            "driving_motor": "getDrivingMotorChanges",
            "alarm_signal": "getAlarmSignalChanges",
        }
        expected_operation_ids = {
            "getLatestVehicleStatus",
            "getOdometerReports",
            *change_operation_ids.values(),
            *ON_DEMAND_OPERATION_IDS.values(),
        }

        self.assertEqual(
            set(NioDataUpdateCoordinator._CHANGE_ENDPOINTS),
            expected_change_resources,
        )
        self.assertEqual(len(expected_operation_ids), 24)
        self.assertTrue(hasattr(NioApiClient, "async_get_latest_vehicle_record"))
        self.assertTrue(hasattr(NioApiClient, "async_get_odometer_report"))
        self.assertEqual(
            expected_operation_ids,
            {
                "getLatestVehicleStatus",
                "getWindowStatusChanges",
                "getVehicleStatusChanges",
                "getTripStatusChanges",
                "getSOCStatusChanges",
                "getPositionStatusChanges",
                "getASRFileList",
                "getLightStatusChanges",
                "getHVACStatusChanges",
                "getHeatingStatusChanges",
                "getFridgeStatusChanges",
                "getExtremumDataChanges",
                "getDrivingMotorChanges",
                "getDrivingDataChanges",
                "getDoorStatusChanges",
                "getCellStatusChanges",
                "getAlarmSignalChanges",
                "getDlbSnapshot",
                "getDlbEvent",
                "extractDlbSnapshot",
                "downloadDlbEvent",
                "getVehicleRecallHistory",
                "getOdometerReports",
                "getRecallCampaigns",
            },
        )
