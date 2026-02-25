"""
Application-wide constants, hardware limits, and default values.

All hard-coded numbers that were previously scattered across the monolithic
script are centralised here so they can be tuned from a single place.
"""

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
APP_TITLE = "ChipSHOUTER GUI Control"
APP_MIN_WIDTH = 800
APP_MIN_HEIGHT = 700

# ---------------------------------------------------------------------------
# Probe-tip pulse-width limits
# Each entry maps probe name -> { v_min, v_max, table }
# table is a list of (voltage, pw_min, pw_max) used for linear interpolation.
# ---------------------------------------------------------------------------
PROBE_LIMITS = {
    "4mm": {
        "v_min": 125,
        "v_max": 400,
        "table": [
            (125, 38, 500),
            (150, 35, 400),
            (200, 30, 270),
            (250, 27, 200),
            (300, 24, 160),
            (325, 28, 140),
            (350, 26, 130),
            (400, 25, 105),
        ],
    },
    "1mm": {
        "v_min": 110,
        "v_max": 300,
        "table": [
            (110, 33, 82),
            (150, 26, 55),
            (200, 21, 38),
            (250, 18, 28),
            (290, 16, 22),
            (300, 16, 20),
        ],
    },
}

# ---------------------------------------------------------------------------
# Device configuration defaults (basic-mode sliders)
# ---------------------------------------------------------------------------
DEFAULT_VOLTAGE = 300
DEFAULT_PULSE_WIDTH = 160
DEFAULT_PULSE_REPEAT = 1
DEFAULT_DEADTIME = 10

VOLTAGE_RANGE = (125, 400)  # global slider bounds before probe override
PULSE_WIDTH_RANGE = (24, 160)
PULSE_REPEAT_RANGE = (1, 10000)
DEADTIME_RANGE = (1, 1000)

# ---------------------------------------------------------------------------
# Serial terminal defaults
# ---------------------------------------------------------------------------
BAUD_RATES = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
DEFAULT_BAUD = "115200"

SERIAL_POLL_INTERVAL_MS = 150  # timer interval for reading serial data
SERIAL_READ_TIMEOUT = 0.1  # serial.Serial timeout (seconds)

# ---------------------------------------------------------------------------
# Polling intervals (ms)
# ---------------------------------------------------------------------------
FAULT_POLL_INTERVAL_MS = 3000
ARM_STATE_POLL_INTERVAL_MS = 700
API_OPERATION_TIMEOUT_MS = 5000

# ---------------------------------------------------------------------------
# Sweep defaults
# ---------------------------------------------------------------------------
SWEEP_V_START = 200
SWEEP_V_END = 400
SWEEP_V_STEP = 50

SWEEP_PW_START = 80
SWEEP_PW_END = 480
SWEEP_PW_STEP = 40

SWEEP_PW_SLIDER_MIN = 16
SWEEP_PW_SLIDER_MAX = 500

SWEEP_DELAY_START = 0
SWEEP_DELAY_END = 0
SWEEP_DELAY_STEP = 5
SWEEP_DELAY_RANGE = (0, 125)

SWEEP_PULSES_PER_POINT = 5
SWEEP_PULSE_REPEAT = 1
SWEEP_PULSE_INTERVAL = 2  # seconds between pulses within a point
SWEEP_DEADTIME = 10

# ---------------------------------------------------------------------------
# KW45 target protocol marker
# ---------------------------------------------------------------------------
KW45_RESET_MARKER = "KW45 Ready. Waiting for commands..."

# ---------------------------------------------------------------------------
# Repeat-send defaults
# ---------------------------------------------------------------------------
REPEAT_SEND_INTERVAL_RANGE = (10, 600_000)  # ms
REPEAT_SEND_DEFAULT_INTERVAL = 1000
REPEAT_SEND_DEFAULT_PAYLOAD = "START"
