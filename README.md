# ChipSHOUTER GUI Control

A PySide6 desktop application for controlling the [ChipSHOUTER](https://www.newae.com/chipshouter) electromagnetic fault injection (EMFI) device, with integrated serial terminal for target board communication and automated parameter-sweep fault-injection campaigns.

The application is designed for hardware security research — it drives high-voltage EM pulses into a target (specifically an NXP **KW45** microcontroller) and detects glitches in AES cryptographic operations.

## Features

### Device Control (Basic Mode)
- Connect/disconnect to ChipSHOUTER over serial port
- Configure voltage, pulse width, pulse repeat, and deadtime via sliders
- Probe tip selection (4 mm / 1 mm) with automatic voltage and pulse-width limit enforcement
- Hardware trigger mode (Active-High / Active-Low) and termination (Hi-Z / 50 Ω)
- ARM / DISARM with strong visual feedback (color-coded buttons and borders)
- Single-pulse fire, mute buzzer, hardware reset
- Automatic fault polling and ARM state synchronization

### Serial Terminal
- Independent serial connection to a target board (e.g. KW45) with configurable baud rate
- Quick-send controls for `MODE:<n>` and `START` commands
- Repeat-send feature with configurable payload and interval
- Export terminal log to CSV

### Sweep Scan
- Automated multi-axis parameter sweep over any combination of **Voltage**, **Pulse Width**, and **Trigger Delay**
- Configurable start / end / step for each axis, pulses per point, pulse interval, and target test mode
- Response classification: **Glitch** · **Reset** · **Error** · **Normal**
- Automatic baseline CT acquisition and reset recovery
- Progress bar, color-coded results log, and CSV export

### Unified Log Panel
- Combined event and fault log with color coding
- Read / clear current and latched faults

## Architecture

```
ChipShouter/
├── main.py                 # Entry point
├── config.py               # Constants, limits, defaults
├── requirements.txt        # Dependencies
├── ui/
│   ├── main_window.py      # Controller — wires panels ↔ workers
│   ├── theme.py            # Dark-theme QSS stylesheet
│   └── panels/
│       ├── basic_panel.py      # Device connection + config + actions
│       ├── terminal_panel.py   # Serial terminal UI
│       ├── sweep_panel.py      # Sweep scan config + results
│       └── log_panel.py        # Unified log + fault controls
├── workers/
│   ├── shouter_worker.py   # ChipSHOUTER device I/O (QThread)
│   ├── serial_worker.py    # Target board serial I/O (QThread)
│   └── sweep_worker.py     # Sweep campaign logic (QThread)
└── utils/
    ├── serial_utils.py     # Port enumeration helpers
    └── csv_export.py       # CSV export helpers
```

- **Panels** are pure UI widgets with no business logic.
- **Workers** run on dedicated `QThread` instances — all hardware I/O stays off the GUI thread.
- **MainWindow** acts as the controller, wiring signals/slots between panels and workers.

## Requirements

| Package | Version | Purpose |
|---------|---------|---------|
| [PySide6](https://pypi.org/project/PySide6/) | ≥ 6.5, < 7 | Qt 6 GUI framework |
| [pyserial](https://pypi.org/project/pyserial/) | ≥ 3.5, < 4 | Serial communication with target board |
| [chipshouter](https://pypi.org/project/chipshouter/) | ≥ 1.0 | NewAE ChipSHOUTER Python API |

## Getting Started

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python main.py
```

## Hardware Setup

Two separate serial (COM) ports are required:

1. **ChipSHOUTER** — connects via the `chipshouter` library (USB-serial).
2. **KW45 target board** — connects via raw serial (`pyserial`).

> The two connections cannot share the same port; the UI enforces this with a port-conflict mutex.

### Probe Tips

Select the correct probe tip **before** configuring voltage and pulse width. Each tip has different operating envelopes:

| Probe | Voltage Range | Pulse Width Range |
|-------|--------------|-------------------|
| 4 mm  | 125 – 400 V  | 25 – 500 ns (varies by voltage) |
| 1 mm  | 110 – 300 V  | 16 – 82 ns (varies by voltage)  |

### Sweep Prerequisites

Both the ChipSHOUTER and Serial Terminal must be connected before starting a sweep. During a sweep the application takes exclusive control of both connections.

## Configuration

All tunable constants are centralized in `config.py`: voltage/pulse-width ranges, probe limit interpolation tables, default slider values, baud rates, polling intervals, sweep defaults, the KW45 reset marker string, and repeat-send defaults.

## License

This project is for internal research use.
