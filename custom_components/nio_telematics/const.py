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

# NIO grants the application's full permitted scope set when the OAuth
# authorization request omits ``scope``. Do not send an explicit list: NIO
# rejects the entire request if it contains a scope unavailable to that app.
OAUTH_SCOPE_REVISION: Final = 2

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=10)
ATTR_EVENT_TIME: Final = "event_time"

CHANGE_ENDPOINTS: Final[tuple[str, ...]] = (
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
)
CHANGE_ENDPOINT_RESOURCES: Final[dict[str, str]] = {
    "vehicle_status_changes": "vehicle_status",
}
SUPPORTED_ENDPOINTS: Final[tuple[str, ...]] = (
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
)
