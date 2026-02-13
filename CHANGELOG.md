# Change Log

## 2026-02-13
- Removed Expert Mode from `shouter_gui.py`:
  - Removed Expert Mode tab, code editor, and execution log UI.
  - Removed `CodeExecutionWorker` and related thread lifecycle handling.
  - Removed Expert Mode callbacks and log routing to expert log view.
- Kept Basic Mode and Serial Terminal tabs.
- Preserved ARM polling/state sync and MUTE button visual behavior.

## 2026-02-13 (Recent Updates)
- Improved ARM visual feedback:
  - Stronger armed/disarmed button styles and clearer armed text state.
- Added terminal quick controls:
  - Quick send for `MODE:x` and `START` in Serial Terminal panel.
- Added repeated terminal send feature:
  - Configurable payload and interval (ms), with start/stop controls.
  - Automatic stop on terminal disconnect/close.
- Reworked window structure to fixed 3-pane layout:
  - Top-left: ChipSHOUTER settings.
  - Top-right: Serial Terminal.
  - Bottom: unified Log Panel.
  - Disabled dock dragging/floating for fixed positions.
- Simplified logs:
  - Merged Event Log and Fault Log into one panel.
  - Kept fault action buttons (`Read Current`, `Read Latched`, `Clear Faults`) in unified log header.
- Updated CSV export behavior:
  - Removed Event/Fault export buttons.
  - Kept terminal export only.
  - Terminal CSV export now writes one raw message per row (single-column output).

## Notes
- This file is intended to record each functional/code update in this folder.
