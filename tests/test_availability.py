"""Tests for endpoint availability summaries."""

import unittest

from _load import load_module

availability = load_module("availability")


class TestAvailability(unittest.TestCase):
    def test_overall_availability(self) -> None:
        self.assertEqual(
            availability.overall_availability(
                {"vehicle_status": "success", "soc_status": "no_recent_data"}
            ),
            "available",
        )
        self.assertEqual(
            availability.overall_availability(
                {"vehicle_status": "success", "door_status": "permission_denied"}
            ),
            "partial",
        )
        self.assertEqual(
            availability.overall_availability(
                {"door_status": "permission_denied"}
            ),
            "unavailable",
        )

    def test_attributes_group_endpoint_results(self) -> None:
        attributes = availability.availability_attributes(
            {
                "vehicle_status": "success",
                "soc_status": "no_recent_data",
                "door_status": "permission_denied",
                "trip_status": "NioApiError",
            }
        )

        self.assertEqual(attributes["working_endpoints"], ["vehicle_status"])
        self.assertEqual(attributes["empty_endpoints"], ["soc_status"])
        self.assertEqual(
            attributes["permission_denied_endpoints"], ["door_status"]
        )
        self.assertEqual(
            attributes["error_endpoints"], {"trip_status": "NioApiError"}
        )
