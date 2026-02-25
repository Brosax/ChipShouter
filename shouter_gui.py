import sys
import time
import csv
import serial
import serial.tools.list_ports
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QSlider, QLabel, QTextEdit, QComboBox,
                             QSpinBox, QGroupBox, QGridLayout, QLineEdit,
                             QSplitter, QFrame, QDockWidget, QFileDialog, QProgressBar)
from PySide6.QtCore import QThread, Signal, QObject, Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
from chipshouter import ChipSHOUTER
from chipshouter.com_tools import Reset_Exception


# --- 工作线程：负责所有串口通信 (Hilo de trabajo) ---
class ShouterWorker(QObject):
    log_signal = Signal(str)
    status_signal = Signal(str)
    reset_detected = Signal()
    fault_signal = Signal(str)  # Emits formatted fault information
    connection_changed = Signal(bool, str)
    armed_changed = Signal(bool)
    busy_changed = Signal(bool)

    request_connect = Signal(str)
    request_disconnect = Signal()
    request_arm = Signal(bool)
    request_fire = Signal()
    request_mute = Signal(bool)
    request_set_voltage = Signal(int)
    request_set_pulse_width = Signal(int)
    request_set_pulse_repeat = Signal(int)
    request_set_deadtime = Signal(int)
    request_set_hwtrig_mode = Signal(bool)
    request_set_hwtrig_term = Signal(bool)
    request_reset = Signal()
    request_read_faults_current = Signal(bool)
    request_read_faults_latched = Signal()
    request_clear_faults = Signal()
    request_read_arm_state = Signal()

    def __init__(self):
        super().__init__()
        self.cs = None
        self.is_connected = False
        self.is_armed = False
        self.is_busy = False
        self.current_port = ""
        self._last_faults_current = None  # Track previous faults to suppress duplicates

        self.request_connect.connect(self.connect_device)
        self.request_disconnect.connect(self.disconnect_device)
        self.request_arm.connect(self.arm_device)
        self.request_fire.connect(self.fire_pulse)
        self.request_mute.connect(self.toggle_mute)
        self.request_set_voltage.connect(self.set_voltage)
        self.request_set_pulse_width.connect(self.set_pulse_width)
        self.request_set_pulse_repeat.connect(self.set_pulse_repeat)
        self.request_set_deadtime.connect(self.set_deadtime)
        self.request_set_hwtrig_mode.connect(self.set_hwtrig_mode)
        self.request_set_hwtrig_term.connect(self.set_hwtrig_term)
        self.request_reset.connect(self.reset_device)
        self.request_read_faults_current.connect(self.read_faults_current)
        self.request_read_faults_latched.connect(self.read_faults_latched)
        self.request_clear_faults.connect(self.clear_faults)
        self.request_read_arm_state.connect(self.read_arm_state)

    def _set_busy(self, busy):
        if self.is_busy != busy:
            self.is_busy = busy
            self.busy_changed.emit(busy)

    def _set_connected(self, connected, port=""):
        if self.is_connected != connected or self.current_port != port:
            self.is_connected = connected
            self.current_port = port
            self.connection_changed.emit(connected, port)

    def _set_armed(self, armed):
        if self.is_armed != armed:
            self.is_armed = armed
            self.armed_changed.emit(armed)

    def _handle_reset(self):
        self._set_armed(False)
        self.reset_detected.emit()

    def connect_device(self, port):
        if self.is_busy:
            self.log_signal.emit("Sistema ocupado, espere...")
            return
        self._set_busy(True)
        try:
            self.cs = ChipSHOUTER(port)
            self._set_connected(True, port)
            self._set_armed(False)
            self.log_signal.emit(f"Conectado a {port}")
        except Exception as e:
            self.cs = None
            self._set_connected(False, "")
            self._set_armed(False)
            self.log_signal.emit(f"Error de conexión: {str(e)}")
        finally:
            self._set_busy(False)

    def disconnect_device(self):
        if self.is_busy:
            return
        self._set_busy(True)
        try:
            if self.is_connected and self.cs:
                try:
                    self.cs.armed = 0  # Disarm before disconnect
                except Exception:
                    pass
            self.cs = None
            self._set_armed(False)
            self._set_connected(False, "")
            self.status_signal.emit("DESCONECTADO")
            self.log_signal.emit("Dispositivo desconectado")
        except Exception as e:
            self.log_signal.emit(f"Error al desconectar: {str(e)}")
        finally:
            self._set_busy(False)

    def arm_device(self, should_arm):
        if not self.is_connected: return
        try:
            self.cs.armed = 1 if should_arm else 0
            self._set_armed(should_arm)
            state = "ARMADO (PELIGRO)" if should_arm else "DESARMADO"
            self.status_signal.emit(state)
            self.log_signal.emit(f"Estado cambiado: {state}")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            self._set_armed(False)
            self.log_signal.emit(f"Error al cambiar armado: {str(e)}")

    def fire_pulse(self):
        if not self.is_connected: return
        try:
            self.cs.pulse = 1
            self.log_signal.emit("¡Pulso disparado!")
        except Reset_Exception:
            self._handle_reset()

    def toggle_mute(self, mute_enabled):
        if not self.is_connected: return
        try:
            self.cs.mute = 1 if mute_enabled else 0
            state = "SILENCIADO" if mute_enabled else "SONIDO HABILITADO"
            self.log_signal.emit(f"Estado de sonido: {state}")
        except Reset_Exception:
            self._handle_reset()

    def set_voltage(self, voltage):
        if not self.is_connected: return
        try:
            self.cs.voltage = voltage
            self.log_signal.emit(f"Voltaje configurado: {voltage}V")
        except Reset_Exception:
            self._handle_reset()

    def set_pulse_width(self, width):
        if not self.is_connected: return
        try:
            self.cs.pulse.width = width
            self.log_signal.emit(f"Ancho de pulso configurado: {width}ns")
        except Reset_Exception:
            self._handle_reset()

    def set_pulse_repeat(self, repeat):
        if not self.is_connected: return
        try:
            self.cs.pulse.repeat = repeat
            self.log_signal.emit(f"Repeticiones configuradas: {repeat}")
        except Reset_Exception:
            self._handle_reset()

    def set_deadtime(self, deadtime):
        if not self.is_connected: return
        try:
            self.cs.pulse.deadtime = deadtime
            self.log_signal.emit(f"Deadtime configurado: {deadtime}ms")
        except Reset_Exception:
            self._handle_reset()

    def set_hwtrig_mode(self, active_high):
        if not self.is_connected: return
        try:
            self.cs.hwtrig_mode = active_high
            mode_str = "Active-High" if active_high else "Active-Low"
            self.log_signal.emit(f"HW Trigger Mode: {mode_str}")
        except Reset_Exception:
            self._handle_reset()

    def set_hwtrig_term(self, term_50ohm):
        if not self.is_connected: return
        try:
            self.cs.hwtrig_term = term_50ohm
            term_str = "50-ohm" if term_50ohm else "High Impedance (~1.8K-ohm)"
            self.log_signal.emit(f"HW Trigger Termination: {term_str}")
        except Reset_Exception:
            self._handle_reset()

    def reset_device(self):
        if not self.is_connected: return
        try:
            self.cs.reset = True
            self.log_signal.emit("Hardware reset enviado")
        except Reset_Exception:
            self._handle_reset()

    def read_faults_current(self, manual=False):
        if not self.is_connected: return
        try:
            faults = self.cs.faults_current
            # Convert to a comparable representation
            fault_key = tuple(str(f) for f in faults) if faults else ()
            # Only emit if faults changed or it's a manual read
            if fault_key != self._last_faults_current or manual:
                self._last_faults_current = fault_key
                if faults:
                    fault_text = ", ".join(str(f) for f in faults)
                    self.fault_signal.emit(f"[CURRENT] {fault_text}")
                    self.log_signal.emit(f"Faults current: {fault_text}")
                elif manual:
                    self.fault_signal.emit("[CURRENT] No faults")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            if manual:
                self.fault_signal.emit(f"[CURRENT] Error reading faults: {e}")

    def read_faults_latched(self):
        if not self.is_connected: return
        try:
            faults = self.cs.faults_latched
            if faults:
                fault_text = ", ".join(str(f) for f in faults)
                self.fault_signal.emit(f"[LATCHED] {fault_text}")
                self.log_signal.emit(f"Faults latched: {fault_text}")
            else:
                self.fault_signal.emit("[LATCHED] No latched faults")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            self.fault_signal.emit(f"[LATCHED] Error reading faults: {e}")

    def clear_faults(self):
        if not self.is_connected: return
        try:
            self.cs.faults_current = 0
            self._last_faults_current = None  # Reset tracking so next poll picks up changes
            self.fault_signal.emit("[INFO] Faults cleared")
            self.log_signal.emit("Faults cleared")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            self.fault_signal.emit(f"[INFO] Error clearing faults: {e}")

    def read_arm_state(self):
        if not self.is_connected or not self.cs or self.is_busy:
            return
        try:
            armed_value = self.cs.armed
            armed_bool = bool(int(armed_value))
            self._set_armed(armed_bool)
            if armed_bool:
                self.status_signal.emit("ARMADO (PELIGRO)")
            else:
                self.status_signal.emit("DESARMADO")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            self.log_signal.emit(f"Error consultando estado ARM: {str(e)}")

    def send_serial_command(self, command):
        if not self.is_connected:
            self.log_signal.emit("Error: Dispositivo no conectado")
            return
        try:
            # Execute command as Python code with access to device
            local_ns = {'cs': self.cs, 'time': time}
            result = eval(command, local_ns)
            if result is not None:
                self.log_signal.emit(f">>> {command}")
                self.log_signal.emit(f"RX: {result}")
            else:
                self.log_signal.emit(f">>> {command} (OK)")
        except SyntaxError:
            # If eval fails, try exec for statements like assignments
            try:
                local_ns = {'cs': self.cs, 'time': time}
                exec(command, local_ns)
                self.log_signal.emit(f">>> {command} (OK)")
            except Exception as e:
                self.log_signal.emit(f"Error: {str(e)}")
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")

    def execute_code(self, code):
        if not self.is_connected:
            self.log_signal.emit("Error: Dispositivo no conectado")
            return
        try:
            # Create a local namespace with the device
            local_ns = {'cs': self.cs, 'time': time, 'Reset_Exception': Reset_Exception}
            exec(code, local_ns)
            self.log_signal.emit("Código ejecutado correctamente")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            self.log_signal.emit(f"Error de ejecución: {str(e)}")


# --- Serial Terminal Worker ---
class SerialTerminalWorker(QObject):
    data_received = Signal(str)
    status_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.is_connected = False
        self.running = False
        self.last_sent_command = ""
        self.is_reading = False  # Prevent re-entrant reads

    def connect_serial(self, port, baudrate):
        try:
            # Close existing connection if any
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            self.is_connected = True
            self.running = True
            self.is_reading = False
            self.status_signal.emit(f"Terminal conectado a {port} @ {baudrate} baud")
        except Exception as e:
            self.status_signal.emit(f"Error de conexión: {str(e)}")

    def disconnect_serial(self):
        self.running = False
        self.is_reading = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.serial_port = None
        self.status_signal.emit("Terminal desconectado")

    def send_data(self, data):
        if self.is_connected and self.serial_port:
            try:
                self.last_sent_command = data
                self.serial_port.write((data + '\r\n').encode())
                self.data_received.emit(f"> {data}\n")
            except Exception as e:
                self.status_signal.emit(f"Error TX: {str(e)}")

    def read_data(self):
        # Prevent re-entrant calls
        if self.is_reading:
            return
        if not self.is_connected or not self.serial_port or not self.serial_port.is_open:
            return
            
        self.is_reading = True
        try:
            if self.serial_port.in_waiting:
                data = self.serial_port.read(self.serial_port.in_waiting).decode(errors='ignore')
                if data and data.strip():
                    self.data_received.emit(data)
        except Exception as e:
            pass
        finally:
            self.is_reading = False

# --- Sweep Worker: KW45 fault injection with external hardware trigger ---
class SweepWorker(QObject):
    progress_signal = Signal(int, int, str)  # current, total, info
    result_signal = Signal(dict)
    sweep_finished = Signal(str)
    log_signal = Signal(str)
    _start_requested = Signal(object, object, dict)  # cs, serial_port, config

    RESET_MARKER = "KW45 Ready. Waiting for commands..."

    def __init__(self):
        super().__init__()
        self._start_requested.connect(self.start_sweep)
        self.cs = None
        self._stop_requested = False
        self.is_running = False
        self.results = []
        self._warned_no_trigger_offset = False

    # ---- public API ----
    def start_sweep(self, cs, target_serial, config):
        """
        Run parameter sweep using the KW45 external-trigger workflow.
        *target_serial* is the already-open serial.Serial from the Serial Terminal.
        """
        self.cs = cs
        self._stop_requested = False
        self.is_running = True
        self.results = []
        self.reset_count = 0
        self._warned_no_trigger_offset = False

        if not target_serial or not target_serial.is_open:
            self.log_signal.emit("ERROR: Serial Terminal must be connected to the target board.")
            self.is_running = False
            self.sweep_finished.emit("ABORTED: No target serial connection.")
            return

        ser = target_serial

        # ---- Build sweep grid ----
        voltages = list(range(config['v_start'], config['v_end'] + 1, max(1, config['v_step'])))
        pulse_widths = list(range(config['pw_start'], config['pw_end'] + 1, max(1, config['pw_step'])))
        delays = list(range(config.get('delay_start', 0),
                            config.get('delay_end', 0) + 1,
                            max(1, config.get('delay_step', 1))))
        if not delays:
            delays = [0]

        total = len(voltages) * len(pulse_widths) * len(delays)
        n_pulses = config.get('pulses_per_point', 5)
        mode = config.get('mode', '1')

        self.log_signal.emit(
            f"Sweep grid: {len(voltages)}V x {len(pulse_widths)}PW x {len(delays)}Delay "
            f"= {total} points, {n_pulses} pulses/point")

        # ---- Fixed params ----
        try:
            self.cs.pulse.repeat = config.get('pulse_repeat', 1)
            self.cs.pulse.deadtime = config.get('deadtime', 10)
            self.cs.mute = 1
            # Configure external hardware trigger (KW45 drives trigger line)
            self.cs.hwtrig_mode = True   # Active-High
            self.cs.hwtrig_term = False  # High impedance
            self.log_signal.emit("HW trigger: external, active-high, hi-Z termination")
        except Exception as e:
            self.log_signal.emit(f"Fixed param config error: {e}")

        # ---- Set KW45 mode & get baseline CT ----
        baseline_ct = self._setup_target_mode(ser, mode)
        if baseline_ct is None and not self._stop_requested:
            self.log_signal.emit("WARNING: Could not obtain baseline CT. Glitch detection may be inaccurate.")

        # ---- ARM once before sweep loop ----
        armed_ok = False
        try:
            self.cs.armed = 1
            time.sleep(0.3)
            armed_ok = True
            self.log_signal.emit("Device armed – starting sweep loop")
        except Reset_Exception:
            self.log_signal.emit("ChipSHOUTER reset on initial ARM")
        except Exception as e:
            self.log_signal.emit(f"Initial arm error: {e}")

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

                    # ---- Configure ChipSHOUTER (no disarm needed) ----
                    try:
                        self.cs.voltage = v
                        self.cs.pulse.width = pw
                        if delay_us > 0:
                            if hasattr(self.cs, "trigger") and hasattr(self.cs.trigger, "offset"):
                                self.cs.trigger.offset = delay_us
                            else:
                                if not self._warned_no_trigger_offset:
                                    self._warned_no_trigger_offset = True
                                    self.log_signal.emit(
                                        "Trigger offset not supported by this ChipSHOUTER library. "
                                        "Delay sweep is ignored.")
                        time.sleep(0.05)
                    except Reset_Exception:
                        self.log_signal.emit(f"ChipSHOUTER reset at V={v} PW={pw}")
                        armed_ok = False
                        continue
                    except Exception as e:
                        self.log_signal.emit(f"Config error V={v} PW={pw}: {e}")
                        continue

                    # ---- Re-arm only if needed (after reset) ----
                    if not armed_ok:
                        try:
                            self.cs.armed = 1
                            time.sleep(0.3)
                            armed_ok = True
                            self.log_signal.emit(f"Re-armed at V={v} PW={pw}")
                        except Reset_Exception:
                            self.log_signal.emit(f"ChipSHOUTER reset on re-arm V={v} PW={pw}")
                            continue
                        except Exception as e:
                            self.log_signal.emit(f"Re-arm error V={v} PW={pw}: {e}")
                            continue

                    glitch = 0
                    error = 0
                    normal = 0
                    reset = 0
                    last_ct = ""

                    for pulse_idx in range(n_pulses):
                        if self._stop_requested:
                            break

                        # Send START -> KW45 encrypts + generates trigger -> ChipSHOUTER fires
                        resp = self._target_exchange(ser)

                        if resp is None:
                            error += 1
                            continue

                        if resp.get('_reset'):
                            # KW45 reset detected
                            reset += 1
                            self.reset_count += 1
                            self.log_signal.emit(
                                f"KW45 RESET #{self.reset_count} at V={v} PW={pw} D={delay_us}µs pulse#{pulse_idx+1}")
                            # Re-configure mode and refresh baseline
                            new_bl = self._setup_target_mode(ser, mode)
                            if new_bl:
                                baseline_ct = new_bl
                                self.log_signal.emit(f"New baseline CT after reset: {baseline_ct}")
                            # Re-arm after KW45 reset
                            try:
                                self.cs.armed = 1
                                time.sleep(0.3)
                                armed_ok = True
                            except Exception:
                                armed_ok = False
                                break
                            continue

                        ct = resp.get('CT', '')
                        last_ct = ct
                        if baseline_ct and ct and ct != baseline_ct:
                            glitch += 1
                        else:
                            normal += 1

                    # (stay armed between test points – no per-point disarm)

                    n_total = glitch + error + normal + reset
                    result = {
                        'voltage': v,
                        'pulse_width': pw,
                        'delay_us': delay_us,
                        'glitches': glitch,
                        'errors': error,
                        'normal': normal,
                        'resets': reset,
                        'total': n_total,
                        'baseline_ct': baseline_ct or '',
                        'last_ct': last_ct,
                        'rate': f"{glitch / n_total * 100:.1f}%" if n_total > 0 else "0%"
                    }
                    self.results.append(result)
                    self.result_signal.emit(result)

                    if glitch > 0:
                        tag = "GLITCH"
                    elif reset > 0:
                        tag = "RESET"
                    elif error > 0:
                        tag = "ERROR"
                    else:
                        tag = "Normal"
                    self.progress_signal.emit(step, total,
                        f"[{step}/{total}] V={v}V PW={pw}ns D={delay_us}µs -> {tag} "
                        f"(G:{glitch} R:{reset} E:{error} N:{normal})")
                    time.sleep(0.05)

        # ---- Cleanup ----
        self._safe_disarm()
        self.is_running = False

        total_g = sum(r['glitches'] for r in self.results)
        total_r = sum(r['resets'] for r in self.results)
        sensitive = len([r for r in self.results if r['glitches'] > 0])
        prefix = 'STOPPED' if self._stop_requested else 'COMPLETE'
        self.sweep_finished.emit(
            f"{prefix}: {step}/{total} points | "
            f"Glitches: {total_g} in {sensitive} points | Resets: {total_r}")

    # ---- internal helpers ----
    def _setup_target_mode(self, ser, mode):
        """Send MODE:<n>, do one clean START exchange, return baseline CT or None."""
        try:
            ser.reset_input_buffer()
            ser.write(f"MODE:{mode}\r\n".encode())
            time.sleep(0.5)
            ser.reset_input_buffer()
            self.log_signal.emit(f"Target MODE:{mode} set")

            # First exchange to get baseline
            resp = self._target_exchange(ser)
            if resp and 'CT' in resp and not resp.get('_reset'):
                self.log_signal.emit(f"Baseline CT: {resp['CT']}")
                return resp['CT']
            return None
        except Exception as e:
            self.log_signal.emit(f"Target mode setup error: {e}")
            return None

    def _target_exchange(self, ser):
        """
        Send START to KW45 and parse the DATA_START / DATA_END response.
        During encryption the KW45 generates a 125µs trigger pulse that
        fires the ChipSHOUTER via external HW trigger.
        Returns dict with parsed fields, or {'_reset': True} on reset, or None on error.
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
                line = raw.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                # Detect KW45 reset
                if self.RESET_MARKER in line:
                    return {'_reset': True}

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

    def _safe_disarm(self):
        """Disarm ChipSHOUTER, with retry."""
        for _ in range(3):
            try:
                if self.cs:
                    self.cs.armed = 0
                    time.sleep(0.15)
                    return
            except Exception:
                time.sleep(0.1)
        # last resort – ignore

    def stop_sweep(self):
        self._stop_requested = True


# --- 主界面 (Ventana Principal) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChipSHOUTER GUI Control")
        self.setMinimumSize(800, 700)

        # Duplicate filter for terminal data
        self.last_terminal_data = ""
        self.last_terminal_time = 0

        # UI Mutex: Track connection states to prevent port conflicts
        self.api_connected = False
        self.api_armed = False
        self.api_busy = False
        self.terminal_connected = False
        self.api_port = None
        self.terminal_port = None
        self.pending_api_action = None

        # 初始化线程 (Inicializar hilo)
        self.worker = ShouterWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # Serial terminal worker
        self.terminal_worker = SerialTerminalWorker()
        self.terminal_thread = QThread()
        self.terminal_worker.moveToThread(self.terminal_thread)
        self.terminal_thread.start()

        # Timer for reading serial data
        self.serial_timer = QTimer()
        self.serial_timer.timeout.connect(self.terminal_worker.read_data)

        # Timer for repeated serial send
        self.repeat_send_timer = QTimer()
        self.repeat_send_timer.timeout.connect(self.send_repeat_payload)

        # Timer for auto-polling faults
        self.fault_timer = QTimer()
        self.fault_timer.timeout.connect(self.poll_faults)

        # Timer for auto-polling armed state
        self.arm_state_timer = QTimer()
        self.arm_state_timer.timeout.connect(self.poll_arm_state)

        # Timeout guard for potentially blocking API operations
        self.api_operation_timeout = QTimer(self)
        self.api_operation_timeout.setSingleShot(True)
        self.api_operation_timeout.timeout.connect(self.on_api_operation_timeout)

        # Sweep worker
        self.sweep_worker = SweepWorker()
        self.sweep_thread = QThread()
        self.sweep_worker.moveToThread(self.sweep_thread)
        self.sweep_thread.start()
        self.sweep_running = False

        self.apply_dark_theme()
        self.setup_ui()
        self.setup_connections()
        self.refresh_action_buttons()

    def apply_dark_theme(self):
        dark_qss = """
        QMainWindow, QWidget {
            background-color: #121212;
            color: #e0e0e0;
        }
        QGroupBox {
            border: 1px solid #444;
            border-radius: 6px;
            margin-top: 12px;
            font-weight: bold;
            color: #ddd;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #333;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 6px;
            color: #fff;
        }
        QPushButton:hover {
            background-color: #444;
            border-color: #666;
        }
        QPushButton:pressed {
            background-color: #222;
            border-color: #444;
        }
        QPushButton:disabled {
            background-color: #1a1a1a;
            color: #555;
            border-color: #333;
        }
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
            background-color: #1e1e1e;
            color: #eee;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 4px;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
            border: 1px solid #007acc;
        }
        QTabWidget::pane {
            border: 1px solid #444;
            top: -1px;
        }
        QTabBar::tab {
            background: #222;
            color: #888;
            padding: 8px 16px;
            border: 1px solid #444;
            border-bottom: none;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background: #333;
            color: #fff;
            border-bottom: 2px solid #007acc;
        }
        QTabBar::tab:hover {
            background: #2a2a2a;
        }
        QScrollBar:vertical {
            background: #121212;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background: #444;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        QLabel { color: #ccc; }
        QDockWidget {
            color: #e0e0e0;
            border: 1px solid #444;
        }
        QDockWidget::title {
            background: #2a2a2a;
            padding-left: 5px;
            padding-top: 2px;
            border-bottom: 1px solid #444;
        }
        """
        self.setStyleSheet(dark_qss)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addStretch(1)
        self.setDockNestingEnabled(False)

        # ========== BASIC MODE TAB ==========
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)

        # ChipSHOUTER connection (inside left/top block)
        conn_group = QGroupBox("ChipSHOUTER Connection")
        conn_layout = QHBoxLayout(conn_group)
        self.port_box = QComboBox()
        self.refresh_ports()
        self.btn_refresh_ports = QPushButton("⟳")
        self.btn_refresh_ports.setFixedWidth(30)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setStyleSheet("background-color: #1b5e20; color: white;")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setStyleSheet("background-color: #bf360c; color: white;")
        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.btn_refresh_ports)
        conn_layout.addWidget(self.port_box)
        conn_layout.addWidget(self.btn_connect)
        conn_layout.addWidget(self.btn_disconnect)
        basic_layout.addWidget(conn_group)

        # Configuration Group
        config_group = QGroupBox("Device Configuration")
        config_grid = QGridLayout(config_group)

        # Voltage
        config_grid.addWidget(QLabel("Voltage (V):"), 0, 0)
        self.voltage_slider = QSlider(Qt.Horizontal)
        self.voltage_slider.setRange(150, 500)
        self.voltage_slider.setValue(300)
        self.voltage_edit = QLineEdit("300")
        self.voltage_edit.setFixedWidth(80)
        self.voltage_edit.setAlignment(Qt.AlignCenter)
        self.voltage_slider.valueChanged.connect(lambda v: self.voltage_edit.setText(str(v)))
        self.voltage_edit.editingFinished.connect(lambda: self._sync_edit_to_slider(self.voltage_edit, self.voltage_slider))
        config_grid.addWidget(self.voltage_slider, 0, 1)
        config_grid.addWidget(self.voltage_edit, 0, 2)
        self.btn_set_voltage = QPushButton("Set")
        config_grid.addWidget(self.btn_set_voltage, 0, 3)

        # Pulse Width
        config_grid.addWidget(QLabel("Pulse Width (ns):"), 1, 0)
        self.pulse_width_slider = QSlider(Qt.Horizontal)
        self.pulse_width_slider.setRange(80, 960)
        self.pulse_width_slider.setValue(160)
        self.pulse_width_edit = QLineEdit("160")
        self.pulse_width_edit.setFixedWidth(80)
        self.pulse_width_edit.setAlignment(Qt.AlignCenter)
        self.pulse_width_slider.valueChanged.connect(lambda v: self.pulse_width_edit.setText(str(v)))
        self.pulse_width_edit.editingFinished.connect(lambda: self._sync_edit_to_slider(self.pulse_width_edit, self.pulse_width_slider))
        config_grid.addWidget(self.pulse_width_slider, 1, 1)
        config_grid.addWidget(self.pulse_width_edit, 1, 2)
        self.btn_set_width = QPushButton("Set")
        config_grid.addWidget(self.btn_set_width, 1, 3)

        # Pulse Repeat
        config_grid.addWidget(QLabel("Pulse Repeat:"), 2, 0)
        self.pulse_repeat_slider = QSlider(Qt.Horizontal)
        self.pulse_repeat_slider.setRange(1, 10000)
        self.pulse_repeat_slider.setValue(1)
        self.pulse_repeat_edit = QLineEdit("1")
        self.pulse_repeat_edit.setFixedWidth(80)
        self.pulse_repeat_edit.setAlignment(Qt.AlignCenter)
        self.pulse_repeat_slider.valueChanged.connect(lambda v: self.pulse_repeat_edit.setText(str(v)))
        self.pulse_repeat_edit.editingFinished.connect(lambda: self._sync_edit_to_slider(self.pulse_repeat_edit, self.pulse_repeat_slider))
        config_grid.addWidget(self.pulse_repeat_slider, 2, 1)
        config_grid.addWidget(self.pulse_repeat_edit, 2, 2)
        self.btn_set_repeat = QPushButton("Set")
        config_grid.addWidget(self.btn_set_repeat, 2, 3)

        # Deadtime
        config_grid.addWidget(QLabel("Deadtime (ms):"), 3, 0)
        self.deadtime_slider = QSlider(Qt.Horizontal)
        self.deadtime_slider.setRange(1, 1000)
        self.deadtime_slider.setValue(10)
        self.deadtime_edit = QLineEdit("10")
        self.deadtime_edit.setFixedWidth(80)
        self.deadtime_edit.setAlignment(Qt.AlignCenter)
        self.deadtime_slider.valueChanged.connect(lambda v: self.deadtime_edit.setText(str(v)))
        self.deadtime_edit.editingFinished.connect(lambda: self._sync_edit_to_slider(self.deadtime_edit, self.deadtime_slider))
        config_grid.addWidget(self.deadtime_slider, 3, 1)
        config_grid.addWidget(self.deadtime_edit, 3, 2)
        self.btn_set_deadtime = QPushButton("Set")
        config_grid.addWidget(self.btn_set_deadtime, 3, 3)

        # HW Trigger Mode
        config_grid.addWidget(QLabel("HW Trigger Mode:"), 4, 0)
        self.hwtrig_mode_box = QComboBox()
        self.hwtrig_mode_box.addItems(["Active-High", "Active-Low"])
        config_grid.addWidget(self.hwtrig_mode_box, 4, 1)
        self.btn_set_hwtrig_mode = QPushButton("Set")
        config_grid.addWidget(self.btn_set_hwtrig_mode, 4, 2)

        # HW Trigger Termination
        config_grid.addWidget(QLabel("HW Trigger Term:"), 5, 0)
        self.hwtrig_term_box = QComboBox()
        self.hwtrig_term_box.addItems(["High Impedance (~1.8K)","50-ohm"])
        config_grid.addWidget(self.hwtrig_term_box, 5, 1)
        self.btn_set_hwtrig_term = QPushButton("Set")
        config_grid.addWidget(self.btn_set_hwtrig_term, 5, 2)

        # Reset
        self.btn_reset_device = QPushButton("Reset Device")
        self.btn_reset_device.setStyleSheet("background-color: #b71c1c; color: white;")
        config_grid.addWidget(self.btn_reset_device, 6, 0, 1, 3)

        # Apply All button
        self.btn_apply_all = QPushButton("Apply All Settings")
        self.btn_apply_all.setStyleSheet("background-color: #01579b; color: white;")
        config_grid.addWidget(self.btn_apply_all, 7, 0, 1, 3)

        basic_layout.addWidget(config_group)

        # Action Buttons
        action_group = QGroupBox("Actions")
        action_layout = QHBoxLayout(action_group)
        self.btn_arm = QPushButton("ARM")
        self.btn_arm.setStyleSheet(
            "QPushButton {background-color: #c62828; color: white; font-weight: 900; "
            "font-size: 14px; border: 2px solid #ff8a80;}"
            "QPushButton:disabled {background-color: #c62828; color: white; font-weight: 900; "
            "font-size: 14px; border: 2px solid #ff8a80;}"
        )
        self.btn_arm.setFixedHeight(50)
        self.btn_disarm = QPushButton("DISARM")
        self.btn_disarm.setStyleSheet("background-color: #1b5e20; font-weight: 900; color: white; border: 1px solid #66bb6a;")
        self.btn_disarm.setFixedHeight(50)
        self.btn_disarm.setEnabled(False)  # Start in disarmed state
        self.btn_pulse = QPushButton("PULSE")
        self.btn_pulse.setStyleSheet("background-color: #e64a19; font-weight: bold; color: white;")
        self.btn_pulse.setFixedHeight(50)
        self.btn_pulse.setEnabled(False)  # Can't pulse when disarmed
        self.btn_mute = QPushButton("MUTE SOUND")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedHeight(50)
        self.btn_mute.setStyleSheet(
            "QPushButton {background-color: #37474f; color: white;}"
            "QPushButton:checked {background-color: #ffb300; color: black; font-weight: bold;}"
        )
        self.update_mute_button_appearance(False)
        action_layout.addWidget(self.btn_arm)
        action_layout.addWidget(self.btn_disarm)
        action_layout.addWidget(self.btn_pulse)
        action_layout.addWidget(self.btn_mute)
        basic_layout.addWidget(action_group)

        self.dock_basic_mode = QDockWidget("Basic Mode", self)
        self.dock_basic_mode.setObjectName("dock_basic_mode")
        self.dock_basic_mode.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.dock_basic_mode.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_basic_mode.setTitleBarWidget(QWidget())
        self.dock_basic_mode.setWidget(basic_tab)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_basic_mode)

        # ========== SERIAL TERMINAL TAB ==========
        terminal_tab = QWidget()
        terminal_layout = QVBoxLayout(terminal_tab)

        # Terminal connection settings
        term_conn_group = QGroupBox("Serial Connection")
        term_conn_layout = QHBoxLayout(term_conn_group)
        term_conn_layout.addWidget(QLabel("Port:"))
        self.term_port_box = QComboBox()
        self.refresh_terminal_ports()
        self.term_port_box.setMinimumWidth(100)
        term_conn_layout.addWidget(self.term_port_box)
        self.btn_term_refresh = QPushButton("⟳")
        self.btn_term_refresh.setFixedWidth(30)
        term_conn_layout.addWidget(self.btn_term_refresh)
        term_conn_layout.addWidget(QLabel("Baud:"))
        self.baud_box = QComboBox()
        self.baud_box.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.baud_box.setCurrentText("115200")
        term_conn_layout.addWidget(self.baud_box)
        term_conn_layout.addStretch()
        self.btn_term_connect = QPushButton("Connect")
        self.btn_term_connect.setStyleSheet("background-color: #1b5e20; color: white;")
        self.btn_term_disconnect = QPushButton("Disconnect")
        self.btn_term_disconnect.setStyleSheet("background-color: #bf360c; color: white;")
        term_conn_layout.addWidget(self.btn_term_connect)
        term_conn_layout.addWidget(self.btn_term_disconnect)
        terminal_layout.addWidget(term_conn_group)

        # Quick test-board controls
        quick_group = QGroupBox("Test Board Quick Control")
        quick_layout = QHBoxLayout(quick_group)
        quick_layout.addWidget(QLabel("Mode:"))
        self.test_mode_box = QComboBox()
        self.test_mode_box.addItems(["1", "2", "3", "4"])
        self.test_mode_box.setCurrentText("1")
        quick_layout.addWidget(self.test_mode_box)
        self.btn_send_mode = QPushButton("Send MODE")
        self.btn_send_mode.setStyleSheet("background-color: #1565c0; color: white;")
        quick_layout.addWidget(self.btn_send_mode)
        self.btn_send_signal = QPushButton("Send START Signal")
        self.btn_send_signal.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        quick_layout.addWidget(self.btn_send_signal)
        quick_layout.addStretch()
        terminal_layout.addWidget(quick_group)

        # Terminal output
        term_log_header = QHBoxLayout()
        term_log_header.addWidget(QLabel("Terminal Log:"))
        self.btn_export_terminal_csv = QPushButton("Export CSV")
        self.btn_export_terminal_csv.setStyleSheet("background-color: #1565c0; color: white;")
        self.btn_export_terminal_csv.setFixedHeight(24)
        term_log_header.addWidget(self.btn_export_terminal_csv)
        term_log_header.addStretch()
        terminal_layout.addLayout(term_log_header)

        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Consolas", 10))
        self.terminal_output.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        terminal_layout.addWidget(self.terminal_output)

        # Command input
        cmd_layout = QHBoxLayout()
        self.terminal_input = QLineEdit()
        self.terminal_input.setFont(QFont("Consolas", 10))
        self.terminal_input.setPlaceholderText("Enter command and press Enter or Send...")
        self.btn_send_cmd = QPushButton("Send")
        self.btn_send_cmd.setStyleSheet("background-color: #01579b; color: white;")
        self.btn_clear_term = QPushButton("Clear")
        cmd_layout.addWidget(self.terminal_input)
        cmd_layout.addWidget(self.btn_send_cmd)
        cmd_layout.addWidget(self.btn_clear_term)
        terminal_layout.addLayout(cmd_layout)

        # Repeat send controls
        repeat_group = QGroupBox("Repeat Send")
        repeat_layout = QGridLayout(repeat_group)
        repeat_layout.addWidget(QLabel("Content:"), 0, 0)
        self.repeat_payload_input = QLineEdit()
        self.repeat_payload_input.setPlaceholderText("e.g. START or MODE:1")
        self.repeat_payload_input.setText("START")
        repeat_layout.addWidget(self.repeat_payload_input, 0, 1, 1, 3)

        repeat_layout.addWidget(QLabel("Interval:"), 1, 0)
        self.repeat_interval_spin = QSpinBox()
        self.repeat_interval_spin.setRange(10, 600000)
        self.repeat_interval_spin.setValue(1000)
        self.repeat_interval_spin.setSuffix(" ms")
        repeat_layout.addWidget(self.repeat_interval_spin, 1, 1)

        self.btn_repeat_start = QPushButton("Start Repeat")
        self.btn_repeat_start.setStyleSheet("background-color: #6a1b9a; color: white;")
        self.btn_repeat_stop = QPushButton("Stop")
        self.btn_repeat_stop.setStyleSheet("background-color: #424242; color: white;")
        self.btn_repeat_stop.setEnabled(False)
        repeat_layout.addWidget(self.btn_repeat_start, 1, 2)
        repeat_layout.addWidget(self.btn_repeat_stop, 1, 3)
        terminal_layout.addWidget(repeat_group)

        self.dock_terminal_mode = QDockWidget("Serial Terminal", self)
        self.dock_terminal_mode.setObjectName("dock_terminal_mode")
        self.dock_terminal_mode.setAllowedAreas(Qt.RightDockWidgetArea)
        self.dock_terminal_mode.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_terminal_mode.setWidget(terminal_tab)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_terminal_mode)

        # ========== SWEEP SCAN PANEL ==========
        sweep_tab = QWidget()
        sweep_layout = QVBoxLayout(sweep_tab)

        # Info label: target uses Serial Terminal connection
        sweep_info = QLabel("⚡ Uses Serial Terminal connection to target board (ext HW trigger)")
        sweep_info.setStyleSheet("color: #ffab40; font-weight: bold; padding: 4px;")
        sweep_layout.addWidget(sweep_info)

        # Sweep voltage range
        sv_group = QGroupBox("Voltage Sweep (V)")
        sv_grid = QGridLayout(sv_group)
        sv_grid.addWidget(QLabel("Start:"), 0, 0)
        self.sweep_v_start = QSpinBox()
        self.sweep_v_start.setRange(150, 500)
        self.sweep_v_start.setValue(200)
        self.sweep_v_start.setSuffix(" V")
        sv_grid.addWidget(self.sweep_v_start, 0, 1)
        sv_grid.addWidget(QLabel("End:"), 0, 2)
        self.sweep_v_end = QSpinBox()
        self.sweep_v_end.setRange(150, 500)
        self.sweep_v_end.setValue(500)
        self.sweep_v_end.setSuffix(" V")
        sv_grid.addWidget(self.sweep_v_end, 0, 3)
        sv_grid.addWidget(QLabel("Step:"), 0, 4)
        self.sweep_v_step = QSpinBox()
        self.sweep_v_step.setRange(1, 350)
        self.sweep_v_step.setValue(50)
        self.sweep_v_step.setSuffix(" V")
        sv_grid.addWidget(self.sweep_v_step, 0, 5)
        sweep_layout.addWidget(sv_group)

        # Sweep pulse width range
        sp_group = QGroupBox("Pulse Width Sweep (ns)")
        sp_grid = QGridLayout(sp_group)
        sp_grid.addWidget(QLabel("Start:"), 0, 0)
        self.sweep_pw_start = QSpinBox()
        self.sweep_pw_start.setRange(80, 960)
        self.sweep_pw_start.setValue(80)
        self.sweep_pw_start.setSuffix(" ns")
        sp_grid.addWidget(self.sweep_pw_start, 0, 1)
        sp_grid.addWidget(QLabel("End:"), 0, 2)
        self.sweep_pw_end = QSpinBox()
        self.sweep_pw_end.setRange(80, 960)
        self.sweep_pw_end.setValue(480)
        self.sweep_pw_end.setSuffix(" ns")
        sp_grid.addWidget(self.sweep_pw_end, 0, 3)
        sp_grid.addWidget(QLabel("Step:"), 0, 4)
        self.sweep_pw_step = QSpinBox()
        self.sweep_pw_step.setRange(1, 880)
        self.sweep_pw_step.setValue(40)
        self.sweep_pw_step.setSuffix(" ns")
        sp_grid.addWidget(self.sweep_pw_step, 0, 5)
        sweep_layout.addWidget(sp_group)

        # Trigger delay sweep range
        sd_group = QGroupBox("Trigger Delay Sweep (µs)")
        sd_grid = QGridLayout(sd_group)
        sd_grid.addWidget(QLabel("Start:"), 0, 0)
        self.sweep_delay_start = QSpinBox()
        self.sweep_delay_start.setRange(0, 125)
        self.sweep_delay_start.setValue(0)
        self.sweep_delay_start.setSuffix(" µs")
        sd_grid.addWidget(self.sweep_delay_start, 0, 1)
        sd_grid.addWidget(QLabel("End:"), 0, 2)
        self.sweep_delay_end = QSpinBox()
        self.sweep_delay_end.setRange(0, 125)
        self.sweep_delay_end.setValue(0)
        self.sweep_delay_end.setSuffix(" µs")
        sd_grid.addWidget(self.sweep_delay_end, 0, 3)
        sd_grid.addWidget(QLabel("Step:"), 0, 4)
        self.sweep_delay_step = QSpinBox()
        self.sweep_delay_step.setRange(1, 125)
        self.sweep_delay_step.setValue(5)
        self.sweep_delay_step.setSuffix(" µs")
        sd_grid.addWidget(self.sweep_delay_step, 0, 5)
        sweep_layout.addWidget(sd_group)

        # Sweep test parameters
        st_group = QGroupBox("Test Parameters")
        st_grid = QGridLayout(st_group)
        st_grid.addWidget(QLabel("Pulses/Point:"), 0, 0)
        self.sweep_pulses = QSpinBox()
        self.sweep_pulses.setRange(1, 1000)
        self.sweep_pulses.setValue(5)
        st_grid.addWidget(self.sweep_pulses, 0, 1)
        st_grid.addWidget(QLabel("Pulse Repeat:"), 0, 2)
        self.sweep_repeat = QSpinBox()
        self.sweep_repeat.setRange(1, 10000)
        self.sweep_repeat.setValue(1)
        st_grid.addWidget(self.sweep_repeat, 0, 3)
        st_grid.addWidget(QLabel("Deadtime (ms):"), 1, 0)
        self.sweep_deadtime = QSpinBox()
        self.sweep_deadtime.setRange(1, 1000)
        self.sweep_deadtime.setValue(10)
        self.sweep_deadtime.setSuffix(" ms")
        st_grid.addWidget(self.sweep_deadtime, 1, 1)
        st_grid.addWidget(QLabel("Target Mode:"), 1, 2)
        self.sweep_mode_box = QComboBox()
        self.sweep_mode_box.addItems(["1", "2", "3", "4"])
        self.sweep_mode_box.setCurrentText("1")
        st_grid.addWidget(self.sweep_mode_box, 1, 3)
        sweep_layout.addWidget(st_group)

        # Sweep control buttons
        sweep_ctrl = QHBoxLayout()
        self.btn_sweep_start = QPushButton("▶ Start Sweep")
        self.btn_sweep_start.setStyleSheet("background-color: #00695c; color: white; font-weight: bold; font-size: 14px;")
        self.btn_sweep_start.setFixedHeight(40)
        self.btn_sweep_stop = QPushButton("■ Stop")
        self.btn_sweep_stop.setStyleSheet("background-color: #b71c1c; color: white; font-weight: bold; font-size: 14px;")
        self.btn_sweep_stop.setFixedHeight(40)
        self.btn_sweep_stop.setEnabled(False)
        sweep_ctrl.addWidget(self.btn_sweep_start)
        sweep_ctrl.addWidget(self.btn_sweep_stop)
        sweep_layout.addLayout(sweep_ctrl)

        # Progress
        self.sweep_progress = QProgressBar()
        self.sweep_progress.setValue(0)
        self.sweep_progress.setFormat("%v / %m  (%p%)")
        sweep_layout.addWidget(self.sweep_progress)
        self.sweep_status_label = QLabel("Ready")
        self.sweep_status_label.setStyleSheet("color: #aaa;")
        sweep_layout.addWidget(self.sweep_status_label)

        # Sweep results log
        self.sweep_results_log = QTextEdit()
        self.sweep_results_log.setReadOnly(True)
        self.sweep_results_log.setFont(QFont("Consolas", 9))
        self.sweep_results_log.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        sweep_layout.addWidget(self.sweep_results_log)

        # Export
        sweep_export_layout = QHBoxLayout()
        self.btn_sweep_export = QPushButton("Export Sweep CSV")
        self.btn_sweep_export.setStyleSheet("background-color: #1565c0; color: white;")
        self.btn_sweep_clear = QPushButton("Clear")
        sweep_export_layout.addWidget(self.btn_sweep_export)
        sweep_export_layout.addWidget(self.btn_sweep_clear)
        sweep_export_layout.addStretch()
        sweep_layout.addLayout(sweep_export_layout)

        self.dock_sweep = QDockWidget("Sweep Scan", self)
        self.dock_sweep.setObjectName("dock_sweep")
        self.dock_sweep.setAllowedAreas(Qt.RightDockWidgetArea)
        self.dock_sweep.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_sweep.setWidget(sweep_tab)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_sweep)

        self.setup_docks()

        # Force 3-block layout: top-left basic, top-right terminal+sweep tabs, bottom log
        self.splitDockWidget(self.dock_basic_mode, self.dock_terminal_mode, Qt.Horizontal)
        self.tabifyDockWidget(self.dock_terminal_mode, self.dock_sweep)
        self.dock_terminal_mode.raise_()
        self.splitDockWidget(self.dock_basic_mode, self.dock_log, Qt.Vertical)
        self.dock_log.raise_()

    def setup_docks(self):
        # Unified Log Dock (Event + Fault)
        self.dock_log = QDockWidget("Log Panel", self)
        self.dock_log.setObjectName("dock_log")
        self.dock_log.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.dock_log.setFeatures(QDockWidget.NoDockWidgetFeatures)

        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Logs:"))
        self.btn_read_faults = QPushButton("Read Current")
        self.btn_read_faults.setFixedHeight(24)
        self.btn_read_latched = QPushButton("Read Latched")
        self.btn_read_latched.setFixedHeight(24)
        self.btn_clear_faults = QPushButton("Clear Faults")
        self.btn_clear_faults.setFixedHeight(24)
        self.btn_clear_faults.setStyleSheet("background-color: #bf360c; color: white;")
        log_header.addWidget(self.btn_read_faults)
        log_header.addWidget(self.btn_read_latched)
        log_header.addWidget(self.btn_clear_faults)
        self.btn_clear_event_log = QPushButton("Clear")
        self.btn_clear_event_log.setFixedHeight(24)
        log_header.addWidget(self.btn_clear_event_log)
        log_header.addStretch()
        log_layout.addLayout(log_header)

        self.log_view_basic = QTextEdit()
        self.log_view_basic.setReadOnly(True)
        self.log_view_basic.setStyleSheet("background-color: #252526; color: #eee;")
        log_layout.addWidget(self.log_view_basic)

        # Alias for compatibility with existing methods
        self.fault_log_view = self.log_view_basic

        self.dock_log.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_log)

    def setup_connections(self):
        # Connection buttons - ChipSHOUTER (with UI mutex)
        self.btn_connect.clicked.connect(self.connect_api)
        self.btn_disconnect.clicked.connect(self.disconnect_api)
        self.btn_refresh_ports.clicked.connect(self.refresh_ports)

        # Basic mode - Configuration
        self.btn_set_voltage.clicked.connect(lambda: self.worker.request_set_voltage.emit(self.voltage_slider.value()))
        self.btn_set_width.clicked.connect(lambda: self.worker.request_set_pulse_width.emit(self.pulse_width_slider.value()))
        self.btn_set_repeat.clicked.connect(lambda: self.worker.request_set_pulse_repeat.emit(self.pulse_repeat_slider.value()))
        self.btn_set_deadtime.clicked.connect(lambda: self.worker.request_set_deadtime.emit(self.deadtime_slider.value()))
        self.btn_apply_all.clicked.connect(self.apply_all_settings)
        self.btn_set_hwtrig_mode.clicked.connect(lambda: self.worker.request_set_hwtrig_mode.emit(self.hwtrig_mode_box.currentIndex() == 0))
        self.btn_set_hwtrig_term.clicked.connect(lambda: self.worker.request_set_hwtrig_term.emit(self.hwtrig_term_box.currentIndex() == 0))
        self.btn_reset_device.clicked.connect(self.worker.request_reset.emit)

        # Basic mode - Actions
        self.btn_arm.clicked.connect(self.arm_device)
        self.btn_disarm.clicked.connect(self.disarm_device)
        self.btn_pulse.clicked.connect(self.request_pulse)
        self.btn_mute.clicked.connect(lambda: self.worker.request_mute.emit(self.btn_mute.isChecked()))
        self.btn_mute.toggled.connect(self.update_mute_button_appearance)

        # Serial Terminal
        self.btn_term_connect.clicked.connect(self.connect_terminal)
        self.btn_term_disconnect.clicked.connect(self.disconnect_terminal)
        self.btn_term_refresh.clicked.connect(self.refresh_terminal_ports)
        self.btn_send_cmd.clicked.connect(self.send_terminal_command)
        self.terminal_input.returnPressed.connect(self.send_terminal_command)
        self.btn_clear_term.clicked.connect(self.terminal_output.clear)
        self.btn_send_mode.clicked.connect(self.send_test_mode)
        self.btn_send_signal.clicked.connect(self.send_test_signal)
        self.btn_repeat_start.clicked.connect(self.start_repeat_send)
        self.btn_repeat_stop.clicked.connect(self.stop_repeat_send)
        self.btn_export_terminal_csv.clicked.connect(self.export_terminal_log_csv)

        # Terminal worker signals (use UniqueConnection to prevent duplicates)
        self.terminal_worker.data_received.connect(self.append_terminal_data, Qt.UniqueConnection)
        self.terminal_worker.status_signal.connect(self.append_terminal_status, Qt.UniqueConnection)

        # Fault log buttons
        self.btn_read_faults.clicked.connect(lambda: self.worker.request_read_faults_current.emit(True))
        self.btn_read_latched.clicked.connect(self.worker.request_read_faults_latched.emit)
        self.btn_clear_faults.clicked.connect(self.worker.request_clear_faults.emit)
        self.btn_clear_event_log.clicked.connect(self.log_view_basic.clear)

        # Sweep controls
        self.btn_sweep_start.clicked.connect(self.start_sweep)
        self.btn_sweep_stop.clicked.connect(self.stop_sweep)
        self.btn_sweep_export.clicked.connect(self.export_sweep_csv)
        self.btn_sweep_clear.clicked.connect(self.sweep_results_log.clear)
        self.sweep_worker.progress_signal.connect(self.on_sweep_progress)
        self.sweep_worker.result_signal.connect(self.on_sweep_result)
        self.sweep_worker.sweep_finished.connect(self.on_sweep_finished)
        self.sweep_worker.log_signal.connect(self.on_sweep_log)

        # ChipSHOUTER Worker signals
        self.worker.log_signal.connect(self.append_log)
        self.worker.status_signal.connect(self.update_status)
        self.worker.reset_detected.connect(self.handle_reset)
        self.worker.fault_signal.connect(self.append_fault_log)
        self.worker.connection_changed.connect(self.on_api_connection_changed)
        self.worker.armed_changed.connect(self.on_api_armed_changed)
        self.worker.busy_changed.connect(self.on_api_busy_changed)

    def refresh_action_buttons(self):
        controls_enabled = self.api_connected and not self.api_busy

        self.btn_connect.setEnabled((not self.api_connected) and not self.api_busy)
        self.btn_disconnect.setEnabled(self.api_connected and not self.api_busy)

        self.btn_arm.setEnabled(controls_enabled and not self.api_armed)
        self.btn_disarm.setEnabled(controls_enabled and self.api_armed)
        self.btn_pulse.setEnabled(controls_enabled and self.api_armed)

        self.btn_set_voltage.setEnabled(controls_enabled)
        self.btn_set_width.setEnabled(controls_enabled)
        self.btn_set_repeat.setEnabled(controls_enabled)
        self.btn_set_deadtime.setEnabled(controls_enabled)
        self.btn_set_hwtrig_mode.setEnabled(controls_enabled)
        self.btn_set_hwtrig_term.setEnabled(controls_enabled)
        self.btn_reset_device.setEnabled(controls_enabled)
        self.btn_apply_all.setEnabled(controls_enabled)

    def _sync_edit_to_slider(self, edit, slider):
        """Sync a QLineEdit value back to its paired QSlider, clamping to range."""
        try:
            val = int(edit.text())
            val = max(slider.minimum(), min(slider.maximum(), val))
            slider.setValue(val)
        except ValueError:
            edit.setText(str(slider.value()))

    def update_mute_button_appearance(self, muted):
        if muted:
            self.btn_mute.setText("MUTE SOUND")
        else:
            self.btn_mute.setText("MUTE SOUND")

    def on_api_busy_changed(self, busy):
        self.api_busy = busy
        if not busy and self.pending_api_action:
            self.pending_api_action = None
            self.api_operation_timeout.stop()
        self.refresh_action_buttons()

    def on_api_connection_changed(self, connected, port):
        self.api_connected = connected
        self.api_port = port if connected else None
        if connected:
            self.fault_timer.start(3000)
            self.arm_state_timer.start(700)
        else:
            self.fault_timer.stop()
            self.arm_state_timer.stop()
            self.api_armed = False
        self.update_ui_mutex_state()
        self.refresh_action_buttons()

    def on_api_armed_changed(self, armed):
        self.api_armed = armed
        if armed:
            self.btn_arm.setText("ARM")
            self.btn_arm.setStyleSheet(
                "QPushButton {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 3px solid #ffff00;}"
                "QPushButton:disabled {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 3px solid #ffff00;}"
            )
            self.btn_disarm.setText("DISARM")
            self.btn_disarm.setStyleSheet(
                "background-color: #00c853; color: black; font-weight: 900; "
                "font-size: 14px; border: 2px solid #69f0ae;"
            )
        else:
            self.btn_arm.setText("ARM")
            self.btn_arm.setStyleSheet(
                "QPushButton {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 2px solid #ff8a80;}"
                "QPushButton:disabled {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 2px solid #ff8a80;}"
            )
            self.btn_disarm.setText("DISARM")
            self.btn_disarm.setStyleSheet(
                "background-color: #1b5e20; color: white; font-weight: 900; "
                "font-size: 14px; border: 2px solid #66bb6a;"
            )
        self.refresh_action_buttons()

    def on_api_operation_timeout(self):
        if self.pending_api_action:
            self.append_log(f"Timeout en operación API: {self.pending_api_action}")
            self.pending_api_action = None
            self.api_busy = False
            self.refresh_action_buttons()

    def refresh_ports(self):
        # Preserve current selection
        current_port = self.port_box.currentText()
        self.port_box.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.port_box.addItems(ports)
            # Restore previous selection if still available
            if current_port in ports:
                self.port_box.setCurrentText(current_port)
        else:
            self.port_box.addItems(["No ports found"])

    def refresh_terminal_ports(self):
        # Preserve current selection
        current_port = self.term_port_box.currentText()
        self.term_port_box.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.term_port_box.addItems(ports)
            # Restore previous selection if still available
            if current_port in ports:
                self.term_port_box.setCurrentText(current_port)
        else:
            self.term_port_box.addItems(["No ports found"])

    def connect_terminal(self):
        port = self.term_port_box.currentText()
        
        # UI Mutex: Check if this port is already used by ChipSHOUTER API
        if self.api_connected and self.api_port == port:
            self.append_terminal_status(f"Error: Puerto {port} ya está en uso por ChipSHOUTER API. Desconecte primero.")
            return
        
        # Stop timer first if already running
        self.serial_timer.stop()
        # Disconnect first if already connected
        if self.terminal_worker.is_connected:
            self.terminal_worker.disconnect_serial()
        
        baudrate = int(self.baud_box.currentText())
        self.terminal_worker.connect_serial(port, baudrate)
        
        if self.terminal_worker.is_connected:
            self.terminal_connected = True
            self.terminal_port = port
            self.serial_timer.start(150)  # Poll every 150ms
            # Disable ChipSHOUTER connect button for same port
            self.update_ui_mutex_state()

    def disconnect_terminal(self):
        self.serial_timer.stop()
        self.stop_repeat_send()
        self.terminal_worker.disconnect_serial()
        self.terminal_connected = False
        self.terminal_port = None
        self.update_ui_mutex_state()

    def connect_api(self):
        port = self.port_box.currentText()
        if self.api_busy:
            self.append_log("Sistema ocupado, espere...")
            return
        
        # UI Mutex: Check if this port is already used by Serial Terminal
        if self.terminal_connected and self.terminal_port == port:
            self.append_log(f"Error: Puerto {port} ya está en uso por Serial Terminal. Desconecte primero.")
            return

        self.pending_api_action = "connect"
        self.api_operation_timeout.start(5000)
        self.worker.request_connect.emit(port)

    def disconnect_api(self):
        if self.api_busy:
            self.append_log("Sistema ocupado, espere...")
            return

        self.pending_api_action = "disconnect"
        self.api_operation_timeout.start(5000)
        self.worker.request_disconnect.emit()

    def update_ui_mutex_state(self):
        """Update UI elements based on connection states to prevent port conflicts"""
        # If API is connected, show warning in terminal tab for same port
        if self.api_connected and self.api_port:
            if self.term_port_box.currentText() == self.api_port:
                self.btn_term_connect.setToolTip(f"Puerto {self.api_port} en uso por ChipSHOUTER API")
            else:
                self.btn_term_connect.setToolTip("")
        else:
            self.btn_term_connect.setToolTip("")
        
        # If Terminal is connected, show warning in API section for same port
        if self.terminal_connected and self.terminal_port:
            if self.port_box.currentText() == self.terminal_port:
                self.btn_connect.setToolTip(f"Puerto {self.terminal_port} en uso por Serial Terminal")
            else:
                self.btn_connect.setToolTip("")
        else:
            self.btn_connect.setToolTip("")

    def apply_all_settings(self):
        self.worker.request_set_voltage.emit(self.voltage_slider.value())
        self.worker.request_set_pulse_width.emit(self.pulse_width_slider.value())
        self.worker.request_set_pulse_repeat.emit(self.pulse_repeat_slider.value())
        self.worker.request_set_deadtime.emit(self.deadtime_slider.value())
        self.worker.request_set_hwtrig_mode.emit(self.hwtrig_mode_box.currentIndex() == 0)
        self.worker.request_set_hwtrig_term.emit(self.hwtrig_term_box.currentIndex() == 0)

    def arm_device(self):
        if not self.api_connected or self.api_busy:
            return
        self.worker.request_arm.emit(True)

    def disarm_device(self):
        if not self.api_connected or self.api_busy:
            return
        self.worker.request_arm.emit(False)

    def request_pulse(self):
        if not self.api_connected or self.api_busy:
            return
        self.worker.request_fire.emit()

    def send_terminal_command(self):
        cmd = self.terminal_input.text().strip()
        if cmd:
            self.terminal_input.clear()
            self.terminal_worker.send_data(cmd)

    def send_test_mode(self):
        if not self.terminal_worker.is_connected:
            self.append_terminal_status("Error: Terminal no conectado")
            return
        mode = self.test_mode_box.currentText()
        self.terminal_worker.send_data(f"MODE:{mode}")

    def send_test_signal(self):
        if not self.terminal_worker.is_connected:
            self.append_terminal_status("Error: Terminal no conectado")
            return
        self.terminal_worker.send_data("START")

    def start_repeat_send(self):
        if not self.terminal_worker.is_connected:
            self.append_terminal_status("Error: Terminal no conectado")
            return

        payload = self.repeat_payload_input.text().strip()
        if not payload:
            self.append_terminal_status("Error: contenido vacío para envío repetido")
            return

        interval_ms = self.repeat_interval_spin.value()
        self.repeat_send_timer.start(interval_ms)
        self.btn_repeat_start.setEnabled(False)
        self.btn_repeat_stop.setEnabled(True)
        self.append_terminal_status(f"Repeat TX iniciado: '{payload}' cada {interval_ms} ms")

    def stop_repeat_send(self):
        was_running = self.repeat_send_timer.isActive()
        self.repeat_send_timer.stop()
        self.btn_repeat_start.setEnabled(True)
        self.btn_repeat_stop.setEnabled(False)
        if was_running:
            self.append_terminal_status("Repeat TX detenido")

    def send_repeat_payload(self):
        if not self.terminal_worker.is_connected:
            self.stop_repeat_send()
            self.append_terminal_status("Repeat TX detenido: terminal desconectado")
            return

        payload = self.repeat_payload_input.text().strip()
        if not payload:
            self.stop_repeat_send()
            self.append_terminal_status("Repeat TX detenido: contenido vacío")
            return

        self.terminal_worker.send_data(payload)

    def append_terminal_data(self, data):
        # Filter duplicate data received within 500ms
        current_time = time.time()
        if data == self.last_terminal_data and (current_time - self.last_terminal_time) < 0.5:
            return  # Skip duplicate
        
        self.last_terminal_data = data
        self.last_terminal_time = current_time
        
        # Insert data and ensure it ends with newline for proper formatting
        self.terminal_output.moveCursor(QTextCursor.End)
        self.terminal_output.insertPlainText(data)
        if not data.endswith('\n'):
            self.terminal_output.insertPlainText('\n')
        self.terminal_output.moveCursor(QTextCursor.End)

    def append_terminal_status(self, status):
        self.terminal_output.append(f"[{time.strftime('%H:%M:%S')}] {status}\n")
        self.append_log(status)

    def update_status(self, status):
        self.setWindowTitle(f"ChipSHOUTER GUI Control - {status}")

    def append_log(self, text):
        timestamp = f"[{time.strftime('%H:%M:%S')}] {text}"
        # Append to event log
        self.log_view_basic.append(timestamp)
        # Also to terminal if it's a RX message
        if text.startswith("RX:"):
            self.terminal_output.append(text)

    def poll_faults(self):
        """Auto-poll current faults while connected"""
        if self.api_connected:
            self.worker.request_read_faults_current.emit(False)

    def poll_arm_state(self):
        """Auto-poll armed state while connected"""
        if self.api_connected:
            self.worker.request_read_arm_state.emit()

    def append_fault_log(self, text):
        """Append a timestamped entry to the fault log view"""
        timestamp = time.strftime('%H:%M:%S')
        # Color code by type
        if "[CURRENT]" in text and "No faults" not in text and "Error" not in text:
            color = "red"
        elif "[LATCHED]" in text and "No latched" not in text and "Error" not in text:
            color = "#cc6600"
        elif "Error" in text:
            color = "darkred"
        else:
            color = "green"
        self.fault_log_view.append(f"<span style='color:{color};'>[{timestamp}] {text}</span>")
        self.fault_log_view.moveCursor(QTextCursor.End)

    def export_event_log_csv(self):
        self.export_log_to_csv(self.log_view_basic, "event_log")

    def export_fault_log_csv(self):
        self.export_log_to_csv(self.fault_log_view, "fault_log")

    def export_terminal_log_csv(self):
        log_text = self.terminal_output.toPlainText().strip()
        if not log_text:
            self.append_log("No hay datos para exportar (terminal_log)")
            return

        default_file = f"terminal_log_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Terminal Log to CSV",
            default_file,
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                for line in log_text.splitlines():
                    clean_line = line.strip()
                    if clean_line:
                        writer.writerow([clean_line])

            self.append_log(f"Terminal log exportado a CSV: {file_path}")
        except Exception as e:
            self.append_log(f"Error exportando terminal CSV: {str(e)}")

    def export_log_to_csv(self, text_widget, default_name):
        log_text = text_widget.toPlainText().strip()
        if not log_text:
            self.append_log(f"No hay datos para exportar ({default_name})")
            return

        default_file = f"{default_name}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Log to CSV",
            default_file,
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["timestamp", "message", "raw"])
                for line in log_text.splitlines():
                    clean_line = line.strip()
                    if not clean_line:
                        continue
                    ts = ""
                    msg = clean_line
                    if clean_line.startswith("[") and "]" in clean_line:
                        right_idx = clean_line.find("]")
                        ts = clean_line[1:right_idx]
                        msg = clean_line[right_idx + 1:].strip()
                    writer.writerow([ts, msg, clean_line])

            self.append_log(f"Log exportado a CSV: {file_path}")
        except Exception as e:
            self.append_log(f"Error exportando CSV: {str(e)}")

    def handle_reset(self):
        self.api_armed = False
        self.refresh_action_buttons()
        self.append_log("!!! RESET DETECTADO !!! Re-iniciando en 5s...")
        self.append_fault_log("[INFO] !!! HARDWARE RESET DETECTED !!!")

    # ========== SWEEP METHODS ==========
    def start_sweep(self):
        if not self.api_connected:
            self.append_log("Error: ChipSHOUTER not connected. Connect first.")
            return
        if not self.terminal_connected or not self.terminal_worker.is_connected:
            self.append_log("Error: Serial Terminal must be connected to the target board first.")
            return
        if self.sweep_running:
            return
        if not self.worker.cs:
            self.append_log("Error: No ChipSHOUTER device available.")
            return

        # Pause polling & serial timer to avoid conflicts
        self.fault_timer.stop()
        self.arm_state_timer.stop()
        self.serial_timer.stop()
        self.stop_repeat_send()

        self.sweep_running = True
        self.btn_sweep_start.setEnabled(False)
        self.btn_sweep_stop.setEnabled(True)
        self.sweep_results_log.clear()
        self.sweep_progress.setValue(0)

        config = {
            'v_start': self.sweep_v_start.value(),
            'v_end': self.sweep_v_end.value(),
            'v_step': self.sweep_v_step.value(),
            'pw_start': self.sweep_pw_start.value(),
            'pw_end': self.sweep_pw_end.value(),
            'pw_step': self.sweep_pw_step.value(),
            'delay_start': self.sweep_delay_start.value(),
            'delay_end': self.sweep_delay_end.value(),
            'delay_step': self.sweep_delay_step.value(),
            'pulses_per_point': self.sweep_pulses.value(),
            'pulse_repeat': self.sweep_repeat.value(),
            'deadtime': self.sweep_deadtime.value(),
            'mode': self.sweep_mode_box.currentText(),
        }

        # Calculate total points for progress bar
        v_count = len(range(config['v_start'], config['v_end'] + 1, max(1, config['v_step'])))
        pw_count = len(range(config['pw_start'], config['pw_end'] + 1, max(1, config['pw_step'])))
        delays = list(range(config['delay_start'], config['delay_end'] + 1, max(1, config['delay_step'])))
        d_count = max(1, len(delays))
        self.sweep_progress.setMaximum(v_count * pw_count * d_count)

        self.append_log(
            f"Sweep started: V[{config['v_start']}-{config['v_end']}] "
            f"PW[{config['pw_start']}-{config['pw_end']}] "
            f"Delay[{config['delay_start']}-{config['delay_end']}µs]")

        # Emit signal -> Qt auto-uses QueuedConnection -> runs on sweep_thread
        self.sweep_worker._start_requested.emit(
            self.worker.cs, self.terminal_worker.serial_port, config
        )

    def stop_sweep(self):
        self.sweep_worker.stop_sweep()
        self.sweep_status_label.setText("Stopping...")

    def on_sweep_progress(self, current, total, info):
        self.sweep_progress.setValue(current)
        self.sweep_status_label.setText(info)

    def on_sweep_result(self, result):
        v = result['voltage']
        pw = result['pulse_width']
        d = result.get('delay_us', 0)
        g = result['glitches']
        r = result.get('resets', 0)
        e = result['errors']
        n = result['normal']
        rate = result['rate']
        if g > 0:
            color = "#ff5252"
            marker = "*** GLITCH ***"
        elif r > 0:
            color = "#ff6e40"
            marker = "RESET"
        elif e > 0:
            color = "#ffab40"
            marker = "ERROR"
        else:
            color = "#69f0ae"
            marker = "OK"
        self.sweep_results_log.append(
            f"<span style='color:{color};'>V={v:>3}V  PW={pw:>3}ns  D={d:>3}µs  "
            f"G:{g} R:{r} E:{e} N:{n}  Rate:{rate}  [{marker}]</span>"
        )

    def on_sweep_finished(self, summary):
        self.sweep_running = False
        self.btn_sweep_start.setEnabled(True)
        self.btn_sweep_stop.setEnabled(False)
        self.sweep_status_label.setText(summary)
        self.append_log(f"Sweep: {summary}")

        # Resume polling and serial timer
        if self.api_connected:
            self.fault_timer.start(3000)
            self.arm_state_timer.start(700)
        if self.terminal_connected and self.terminal_worker.is_connected:
            self.serial_timer.start(150)

    def on_sweep_log(self, text):
        self.sweep_results_log.append(f"<span style='color:#888;'>[LOG] {text}</span>")
        self.append_log(f"[Sweep] {text}")

    def export_sweep_csv(self):
        results = self.sweep_worker.results
        if not results:
            self.append_log("No sweep data to export.")
            return

        default_file = f"sweep_results_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Sweep Results", default_file,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "voltage_V", "pulse_width_ns", "delay_us",
                    "glitches", "resets", "errors", "normal", "total",
                    "glitch_rate", "baseline_ct", "last_ct"
                ])
                for r in results:
                    writer.writerow([
                        r['voltage'], r['pulse_width'], r.get('delay_us', 0),
                        r['glitches'], r.get('resets', 0), r['errors'], r['normal'],
                        r['total'], r['rate'],
                        r.get('baseline_ct', ''), r.get('last_ct', '')
                    ])
            self.append_log(f"Sweep CSV exported: {file_path}")
        except Exception as e:
            self.append_log(f"Error exporting sweep CSV: {e}")

    def closeEvent(self, event):
        # Stop sweep if running
        if self.sweep_running:
            self.sweep_worker.stop_sweep()
        self.sweep_thread.quit()
        self.sweep_thread.wait()
        # Stop timers
        self.serial_timer.stop()
        self.repeat_send_timer.stop()
        self.fault_timer.stop()
        self.arm_state_timer.stop()
        # Disconnect terminal
        self.terminal_worker.disconnect_serial()
        self.terminal_thread.quit()
        self.terminal_thread.wait()
        # Disconnect ChipSHOUTER
        self.worker.disconnect_device()
        self.worker_thread.quit()
        self.worker_thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())