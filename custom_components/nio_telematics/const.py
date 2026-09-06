"""Constants for NIO Open Telematics."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "nio_telematics"
PLATFORMS: Final = ["sensor"]

API_BASE_URL: Final = "https://open-api-eu.nio.com"
OAUTH_BASE_URL: Final = "https://open-eu.nio.com"
AUTHORIZE_PATH: Final = "/oauth2/authorize"
TOKEN_PATH: Final = "/api/2/oauth/token"
TELEMATICS_PATH: Final = "/api/1/telematics"

CONF_VIN: Final = "vin"
CONF_VEHICLE_NAME: Final = "vehicle_name"
CONF_SCOPE_REVISION: Final = "scope_revision"

OAUTH_SCOPES: Final = [
    "vehicle:connectivity:read",
    "vehicle:body:read",
    "vehicle:dynamics:read",
    "vehicle:location:read",
    "vehicle:energy:read",
    "vehicle:cabin:read",
    "vehicle:powertrain:read",
    "vehicle:diagnostics:read",
    "aftersales:read",
]
OAUTH_SCOPE_REVISION: Final = 1

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=10)
ATTR_EVENT_TIME: Final = "event_time"
