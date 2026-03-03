# Change Log

## 2026-02-27
- Cleaned repository by removing legacy standalone scripts and obsolete files.
- Removed runtime data artifacts (CSV logs, sweep results), caches, and AI tooling configs from tracking.
- Updated `.gitignore` to ignore data exports, caches, and tool config files.
- Added `README.md` with project overview, architecture, setup, and hardware notes.

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

## 2026-03-03
- Sweep glitch detection updated for fixed-key workflow:
  - Added configurable `Expected CT` field in Sweep parameters.
  - If `Expected CT` is provided, CT comparison uses that value directly.
  - If left blank, expected CT auto-locks from first valid target response.
  - CT mismatch now increments `glitches` and stores mismatched CT values.
- Sweep CSV export updated:
  - Removed `baseline_ct` column.
  - Added `glitch_cts` column to persist mismatched CT list per sweep point.
- Sweep interval unit changed to milliseconds:
  - `Pulse Interval` UI label/range/suffix/tooltips switched from seconds to ms.
  - Sweep runtime delay now interprets interval as ms (`ms / 1000`).
- Sweep input ergonomics improved:
  - In `Trigger Delay Sweep` and `Test Parameters`, spinboxes now hide up/down arrows and support keyboard-only numeric editing.
  - Sweep panel content is now vertically scrollable for small-resolution displays.
- Main window adaptive layout improved:
  - Added proportional dock resizing on startup/window resize to keep panels and log area visible on smaller screens.

## Notes
- This file is intended to record each functional/code update in this folder.
