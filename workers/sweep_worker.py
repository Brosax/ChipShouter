"""
SweepWorker – QObject running on a dedicated QThread.

Executes a parameter-sweep fault-injection campaign against a KW45 target
using the ChipSHOUTER's external hardware trigger.  The worker communicates
exclusively through Qt signals so it can run safely off the GUI thread.
"""

import time

from PySide6.QtCore import QObject, Signal

from chipshouter.com_tools import Reset_Exception

from config import KW45_RESET_MARKER


class SweepWorker(QObject):
    # --- outgoing signals ---
    progress_signal = Signal(int, int, str)  # current, total, info
    result_signal = Signal(dict)
    sweep_finished = Signal(str)
    log_signal = Signal(str)

    # --- internal trigger signal (queued connection across threads) ---
    _start_requested = Signal(object, object, dict)  # cs, serial_port, config

    def __init__(self) -> None:
        super().__init__()
        self._start_requested.connect(self.start_sweep)
        self.cs = None
        self._stop_requested = False
        self.is_running = False
        self.results: list[dict] = []
        self._warned_no_trigger_offset = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start_sweep(self, cs, target_serial, config: dict) -> None:
        """
        Run a parameter sweep using the KW45 external-trigger workflow.

        *target_serial* is the already-open ``serial.Serial`` from the
        Serial Terminal panel.
        """
        self.cs = cs
        self._stop_requested = False
        self.is_running = True
        self.results = []
        self.reset_count = 0
        self._warned_no_trigger_offset = False

        if not target_serial or not target_serial.is_open:
            self.log_signal.emit(
                "ERROR: Serial Terminal must be connected to the target board."
            )
            self.is_running = False
            self.sweep_finished.emit("ABORTED: No target serial connection.")
            return

        ser = target_serial

        # ---- Build sweep grid (respect sweep_axes) ----
        axes = config.get("sweep_axes", {"voltage", "pulse_width", "delay"})

        voltages = (
            list(
                range(config["v_start"], config["v_end"] + 1, max(1, config["v_step"]))
            )
            if "voltage" in axes
            else [config["v_start"]]
        )
        pulse_widths = (
            list(
                range(
                    config["pw_start"], config["pw_end"] + 1, max(1, config["pw_step"])
                )
            )
            if "pulse_width" in axes
            else [config["pw_start"]]
        )
        if "delay" in axes:
            delays = list(
                range(
                    config.get("delay_start", 0),
                    config.get("delay_end", 0) + 1,
                    max(1, config.get("delay_step", 1)),
                )
            )
            if not delays:
                delays = [0]
        else:
            delays = [config.get("delay_start", 0)]

        total = len(voltages) * len(pulse_widths) * len(delays)
        n_pulses = config.get("pulses_per_point", 5)
        pulse_interval = config.get("pulse_interval", 2)
        mode = config.get("mode", "1")

        self.log_signal.emit(
            f"Sweep grid: {len(voltages)}V x {len(pulse_widths)}PW x {len(delays)}Delay "
            f"= {total} points, {n_pulses} pulses/point"
        )

        # ---- Fixed params (set while disarmed) ----
        try:
            self.cs.pulse.repeat = config.get("pulse_repeat", 1)
            self.cs.pulse.deadtime = config.get("deadtime", 10)
            self.cs.mute = 1
        except Exception as e:
            self.log_signal.emit(f"Fixed param config error: {e}")

        # ---- Initial clear faults ----
        try:
            self.cs.faults_current = 0
            time.sleep(0.1)
            self.log_signal.emit("Faults cleared")
        except Exception:
            pass

        # ---- Set KW45 mode & get baseline CT ----
        baseline_ct = self._setup_target_mode(ser, mode)
        if baseline_ct is None and not self._stop_requested:
            self.log_signal.emit(
                "WARNING: Could not obtain baseline CT. Glitch detection may be inaccurate."
            )

        step = 0
        for v in voltages:
            if self._stop_requested:
                break
            for pw in pulse_widths:
                if self._stop_requested:
                    break
                for delay_us in delays:
                    if self._stop_requested:
                        break
                    step += 1

                    # 1) Disarm before changing parameters
                    self._safe_disarm()

                    # 2) Set parameters (while disarmed)
                    try:
                        self.cs.voltage = v
                        self.cs.pulse.width = pw
                        if delay_us > 0:
                            if hasattr(self.cs, "trigger") and hasattr(
                                self.cs.trigger, "offset"
                            ):
                                self.cs.trigger.offset = delay_us
                            else:
                                if not self._warned_no_trigger_offset:
                                    self._warned_no_trigger_offset = True
                                    self.log_signal.emit(
                                        "Trigger offset not supported by this ChipSHOUTER library. "
                                        "Delay sweep is ignored."
                                    )
                        time.sleep(0.05)
                    except Reset_Exception:
                        self.log_signal.emit(f"ChipSHOUTER reset at V={v} PW={pw}")
                        continue
                    except Exception as e:
                        self.log_signal.emit(f"Config error V={v} PW={pw}: {e}")
                        continue

                    # 3) Clear faults & Arm
                    if not self._try_clear_and_arm():
                        self.log_signal.emit(f"Arm failed V={v} PW={pw}, skipping")
                        continue

                    # Wait for capacitor charge after arm
                    time.sleep(1.0)

                    # 4) Pulse loop
                    glitch, error, normal, reset = 0, 0, 0, 0
                    last_ct = ""

                    for pulse_idx in range(n_pulses):
                        if self._stop_requested:
                            break

                        if pulse_idx > 0 and pulse_interval > 0:
                            time.sleep(pulse_interval)

                        resp = self._target_exchange(ser)

                        if resp is None:
                            error += 1
                            continue

                        if resp.get("_reset"):
                            reset += 1
                            self.reset_count += 1
                            self.log_signal.emit(
                                f"KW45 RESET #{self.reset_count} at V={v} PW={pw} "
                                f"D={delay_us}us pulse#{pulse_idx + 1}"
                            )
                            new_bl = self._setup_target_mode(ser, mode)
                            if new_bl:
                                baseline_ct = new_bl
                                self.log_signal.emit(
                                    f"New baseline CT after reset: {baseline_ct}"
                                )
                            if not self._try_clear_and_arm():
                                break
                            continue

                        ct = resp.get("CT", "")
                        last_ct = ct
                        if baseline_ct and ct and ct != baseline_ct:
                            glitch += 1
                        else:
                            normal += 1

                    n_total = glitch + error + normal + reset
                    result = {
                        "voltage": v,
                        "pulse_width": pw,
                        "delay_us": delay_us,
                        "glitches": glitch,
                        "errors": error,
                        "normal": normal,
                        "resets": reset,
                        "total": n_total,
                        "baseline_ct": baseline_ct or "",
                        "last_ct": last_ct,
                        "rate": f"{glitch / n_total * 100:.1f}%"
                        if n_total > 0
                        else "0%",
                    }
                    self.results.append(result)
                    self.result_signal.emit(result)

                    tag = (
                        "GLITCH"
                        if glitch > 0
                        else "RESET"
                        if reset > 0
                        else "ERROR"
                        if error > 0
                        else "Normal"
                    )
                    self.progress_signal.emit(
                        step,
                        total,
                        f"[{step}/{total}] V={v}V PW={pw}ns D={delay_us}us -> {tag} "
                        f"(G:{glitch} R:{reset} E:{error} N:{normal})",
                    )
                    time.sleep(0.05)

        # ---- Cleanup ----
        self._safe_disarm()
        self.is_running = False

        total_g = sum(r["glitches"] for r in self.results)
        total_r = sum(r["resets"] for r in self.results)
        sensitive = len([r for r in self.results if r["glitches"] > 0])
        prefix = "STOPPED" if self._stop_requested else "COMPLETE"
        self.sweep_finished.emit(
            f"{prefix}: {step}/{total} points | "
            f"Glitches: {total_g} in {sensitive} points | Resets: {total_r}"
        )

    def stop_sweep(self) -> None:
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _setup_target_mode(self, ser, mode: str):
        """Send MODE:<n>, do one clean START exchange, return baseline CT or None."""
        try:
            ser.reset_input_buffer()
            ser.write(f"MODE:{mode}\r\n".encode())
            time.sleep(0.5)
            ser.reset_input_buffer()
            self.log_signal.emit(f"Target MODE:{mode} set")

            resp = self._target_exchange(ser)
            if resp and "CT" in resp and not resp.get("_reset"):
                self.log_signal.emit(f"Baseline CT: {resp['CT']}")
                return resp["CT"]
            return None
        except Exception as e:
            self.log_signal.emit(f"Target mode setup error: {e}")
            return None

    def _target_exchange(self, ser) -> dict | None:
        """
        Send START to KW45 and parse the DATA_START/DATA_END response.

        Returns dict with parsed fields, ``{'_reset': True}`` on reset,
        or ``None`` on error/timeout.
        """
        try:
            ser.reset_input_buffer()
            ser.write(b"START\r\n")
            data = {}
            collecting = False
            t0 = time.time()
            while (time.time() - t0) < 3.0:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                if KW45_RESET_MARKER in line:
                    return {"_reset": True}

                if "--- DATA_START ---" in line:
                    collecting = True
                    continue
                if "--- DATA_END ---" in line:
                    return data
                if "ERROR:" in line:
                    return None
                if collecting and ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        data[parts[0].strip()] = parts[1].strip()
            return data if data else None
        except Exception:
            return None

    def _safe_disarm(self) -> None:
        """Disarm ChipSHOUTER with retry."""
        for _ in range(3):
            try:
                if self.cs:
                    self.cs.armed = 0
                    time.sleep(0.15)
                    return
            except Exception:
                time.sleep(0.1)

    def _try_clear_and_arm(self) -> bool:
        """Clear faults then arm.  Returns True on success."""
        for attempt in range(3):
            try:
                self.cs.faults_current = 0
                time.sleep(0.1)
                self.cs.armed = 1
                time.sleep(0.2)
                return True
            except Reset_Exception:
                self.log_signal.emit("ChipSHOUTER reset during arm")
                return False
            except Exception as e:
                if attempt < 2:
                    self.log_signal.emit(
                        f"Arm attempt {attempt + 1} failed: {e}, retrying..."
                    )
                    time.sleep(0.3)
                else:
                    self.log_signal.emit(f"Arm failed after 3 attempts: {e}")
        return False
