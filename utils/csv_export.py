"""
CSV export utilities.

Stateless helper functions for exporting log text and sweep results to CSV.
"""

import csv
import time


def export_text_log_to_csv(
    text: str, file_path: str, header: list[str] | None = None
) -> None:
    """
    Export plain-text log content to a CSV file.

    Each non-empty line is written as a row.  If the line starts with
    ``[timestamp]``, the timestamp and message are split into separate columns.

    Parameters
    ----------
    text : str
        The full plain-text log content.
    file_path : str
        Destination CSV path.
    header : list[str] | None
        Optional header row.  Defaults to ``["timestamp", "message", "raw"]``.
    """
    if header is None:
        header = ["timestamp", "message", "raw"]

    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for line in text.splitlines():
            clean = line.strip()
            if not clean:
                continue
            ts = ""
            msg = clean
            if clean.startswith("[") and "]" in clean:
                idx = clean.find("]")
                ts = clean[1:idx]
                msg = clean[idx + 1 :].strip()
            writer.writerow([ts, msg, clean])


def export_raw_lines_to_csv(text: str, file_path: str) -> None:
    """Export raw text lines (e.g. terminal output) to a single-column CSV."""
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        for line in text.splitlines():
            clean = line.strip()
            if clean:
                writer.writerow([clean])


def export_sweep_results_to_csv(results: list[dict], file_path: str) -> None:
    """
    Export sweep result dicts to a CSV with a fixed header.

    Parameters
    ----------
    results : list[dict]
        Each dict must contain keys matching the CSV columns.
    file_path : str
        Destination CSV path.
    """
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "voltage_V",
                "pulse_width_ns",
                "delay_us",
                "glitches",
                "resets",
                "errors",
                "normal",
                "total",
                "glitch_rate",
                "baseline_ct",
                "last_ct",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r["voltage"],
                    r["pulse_width"],
                    r.get("delay_us", 0),
                    r["glitches"],
                    r.get("resets", 0),
                    r["errors"],
                    r["normal"],
                    r["total"],
                    r["rate"],
                    r.get("baseline_ct", ""),
                    r.get("last_ct", ""),
                ]
            )


def default_filename(prefix: str) -> str:
    """Return a default filename like ``prefix_20260225_143012.csv``."""
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
