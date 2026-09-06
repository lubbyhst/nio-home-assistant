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
    "vehicle:read",
    "vehicle:dynamics:read",
    "vehicle:location:read",
    "vehicle:energy:read",
    "vehicle:body:read",
    "vehicle:cabin:read",
    "vehicle:powertrain:read",
    "vehicle:diagnostics:read",
    "vehicle:adas:read",
    "vehicle:nomi:read",
    "aftersales:read",
]

# The explicit scope set changed from the provider-default request. Existing
# entries must reauthenticate so their token is issued with this set.
OAUTH_SCOPE_REVISION: Final = 3

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=10)
ATTR_EVENT_TIME: Final = "event_time"
