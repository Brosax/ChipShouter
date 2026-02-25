"""
ShouterWorker – QObject running on a dedicated QThread.

Handles all ChipSHOUTER serial communication (connect, arm, fire,
parameter changes, fault reads) via signal/slot pairs so the GUI
thread never blocks on I/O.
"""

import time

from PySide6.QtCore import QObject, Signal

from chipshouter import ChipSHOUTER
from chipshouter.com_tools import Reset_Exception


class ShouterWorker(QObject):
    # --- outgoing signals (worker -> UI) ---
    log_signal = Signal(str)
    status_signal = Signal(str)
    reset_detected = Signal()
    fault_signal = Signal(str)
    connection_changed = Signal(bool, str)
    armed_changed = Signal(bool)
    busy_changed = Signal(bool)

    # --- incoming request signals (UI -> worker) ---
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

    def __init__(self) -> None:
        super().__init__()
        self.cs = None
        self.is_connected = False
        self.is_armed = False
        self.is_busy = False
        self.current_port = ""
        self._last_faults_current = None

        # Wire incoming signals to slots
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

    # ------------------------------------------------------------------
    # Internal state helpers
    # ------------------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        if self.is_busy != busy:
            self.is_busy = busy
            self.busy_changed.emit(busy)

    def _set_connected(self, connected: bool, port: str = "") -> None:
        if self.is_connected != connected or self.current_port != port:
            self.is_connected = connected
            self.current_port = port
            self.connection_changed.emit(connected, port)

    def _set_armed(self, armed: bool) -> None:
        if self.is_armed != armed:
            self.is_armed = armed
            self.armed_changed.emit(armed)

    def _handle_reset(self) -> None:
        self._set_armed(False)
        self.reset_detected.emit()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect_device(self, port: str) -> None:
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
            self.log_signal.emit(f"Error de conexión: {e}")
        finally:
            self._set_busy(False)

    def disconnect_device(self) -> None:
        if self.is_busy:
            return
        self._set_busy(True)
        try:
            if self.is_connected and self.cs:
                try:
                    self.cs.armed = 0
                except Exception:
                    pass
            self.cs = None
            self._set_armed(False)
            self._set_connected(False, "")
            self.status_signal.emit("DESCONECTADO")
            self.log_signal.emit("Dispositivo desconectado")
        except Exception as e:
            self.log_signal.emit(f"Error al desconectar: {e}")
        finally:
            self._set_busy(False)

    # ------------------------------------------------------------------
    # Arm / fire / mute
    # ------------------------------------------------------------------
    def arm_device(self, should_arm: bool) -> None:
        if not self.is_connected:
            return
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
            self.log_signal.emit(f"Error al cambiar armado: {e}")

    def fire_pulse(self) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.pulse = 1
            self.log_signal.emit("¡Pulso disparado!")
        except Reset_Exception:
            self._handle_reset()

    def toggle_mute(self, mute_enabled: bool) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.mute = 1 if mute_enabled else 0
            state = "SILENCIADO" if mute_enabled else "SONIDO HABILITADO"
            self.log_signal.emit(f"Estado de sonido: {state}")
        except Reset_Exception:
            self._handle_reset()

    # ------------------------------------------------------------------
    # Parameter setters
    # ------------------------------------------------------------------
    def set_voltage(self, voltage: int) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.voltage = voltage
            self.log_signal.emit(f"Voltaje configurado: {voltage}V")
        except Reset_Exception:
            self._handle_reset()

    def set_pulse_width(self, width: int) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.pulse.width = width
            self.log_signal.emit(f"Ancho de pulso configurado: {width}ns")
        except Reset_Exception:
            self._handle_reset()

    def set_pulse_repeat(self, repeat: int) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.pulse.repeat = repeat
            self.log_signal.emit(f"Repeticiones configuradas: {repeat}")
        except Reset_Exception:
            self._handle_reset()

    def set_deadtime(self, deadtime: int) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.pulse.deadtime = deadtime
            self.log_signal.emit(f"Deadtime configurado: {deadtime}ms")
        except Reset_Exception:
            self._handle_reset()

    def set_hwtrig_mode(self, active_high: bool) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.hwtrig_mode = active_high
            mode_str = "Active-High" if active_high else "Active-Low"
            self.log_signal.emit(f"HW Trigger Mode: {mode_str}")
        except Reset_Exception:
            self._handle_reset()

    def set_hwtrig_term(self, term_50ohm: bool) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.hwtrig_term = term_50ohm
            term_str = "50-ohm" if term_50ohm else "High Impedance (~1.8K-ohm)"
            self.log_signal.emit(f"HW Trigger Termination: {term_str}")
        except Reset_Exception:
            self._handle_reset()

    def reset_device(self) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.reset = True
            self.log_signal.emit("Hardware reset enviado")
        except Reset_Exception:
            self._handle_reset()

    # ------------------------------------------------------------------
    # Fault management
    # ------------------------------------------------------------------
    def read_faults_current(self, manual: bool = False) -> None:
        if not self.is_connected:
            return
        try:
            faults = self.cs.faults_current
            fault_key = tuple(str(f) for f in faults) if faults else ()
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

    def read_faults_latched(self) -> None:
        if not self.is_connected:
            return
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

    def clear_faults(self) -> None:
        if not self.is_connected:
            return
        try:
            self.cs.faults_current = 0
            self._last_faults_current = None
            self.fault_signal.emit("[INFO] Faults cleared")
            self.log_signal.emit("Faults cleared")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            self.fault_signal.emit(f"[INFO] Error clearing faults: {e}")

    def read_arm_state(self) -> None:
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
            self.log_signal.emit(f"Error consultando estado ARM: {e}")

    # ------------------------------------------------------------------
    # Raw command execution (advanced / debug)
    # ------------------------------------------------------------------
    def send_serial_command(self, command: str) -> None:
        if not self.is_connected:
            self.log_signal.emit("Error: Dispositivo no conectado")
            return
        try:
            local_ns = {"cs": self.cs, "time": time}
            result = eval(command, local_ns)
            if result is not None:
                self.log_signal.emit(f">>> {command}")
                self.log_signal.emit(f"RX: {result}")
            else:
                self.log_signal.emit(f">>> {command} (OK)")
        except SyntaxError:
            try:
                local_ns = {"cs": self.cs, "time": time}
                exec(command, local_ns)
                self.log_signal.emit(f">>> {command} (OK)")
            except Exception as e:
                self.log_signal.emit(f"Error: {e}")
        except Exception as e:
            self.log_signal.emit(f"Error: {e}")

    def execute_code(self, code: str) -> None:
        if not self.is_connected:
            self.log_signal.emit("Error: Dispositivo no conectado")
            return
        try:
            local_ns = {"cs": self.cs, "time": time, "Reset_Exception": Reset_Exception}
            exec(code, local_ns)
            self.log_signal.emit("Código ejecutado correctamente")
        except Reset_Exception:
            self._handle_reset()
        except Exception as e:
            self.log_signal.emit(f"Error de ejecución: {e}")
