"""
MainWindow – Top-level application window.

Assembles the dock panels, creates worker threads, and wires all
signal/slot connections.  Business logic lives in the workers;
UI construction lives in the panels.  This class is the "controller"
that ties them together.
"""

import time

from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QTextCursor

from config import (
    APP_MIN_HEIGHT,
    APP_MIN_WIDTH,
    APP_TITLE,
    API_OPERATION_TIMEOUT_MS,
    ARM_STATE_POLL_INTERVAL_MS,
    FAULT_POLL_INTERVAL_MS,
    PROBE_LIMITS,
    SERIAL_POLL_INTERVAL_MS,
)
from ui.theme import DARK_THEME_QSS
from ui.panels.basic_panel import BasicPanel
from ui.panels.terminal_panel import TerminalPanel
from ui.panels.sweep_panel import SweepPanel
from ui.panels.log_panel import LogPanel
from workers.shouter_worker import ShouterWorker
from workers.serial_worker import SerialTerminalWorker
from workers.sweep_worker import SweepWorker
from utils.serial_utils import refresh_port_combobox
from utils.csv_export import (
    default_filename,
    export_raw_lines_to_csv,
    export_sweep_results_to_csv,
    export_text_log_to_csv,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(APP_MIN_WIDTH, APP_MIN_HEIGHT)

        # Terminal duplicate filter
        self.last_terminal_data = ""
        self.last_terminal_time = 0.0

        # UI mutex: track connection states to prevent port conflicts
        self.api_connected = False
        self.api_armed = False
        self.api_busy = False
        self.terminal_connected = False
        self.api_port: str | None = None
        self.terminal_port: str | None = None
        self.pending_api_action: str | None = None

        # -- Workers & threads --
        self._setup_workers()

        # -- Timers --
        self._setup_timers()

        # -- UI --
        self.setStyleSheet(DARK_THEME_QSS)
        self._setup_panels()
        self._setup_connections()
        self._refresh_action_buttons()

        # Sweep state
        self.sweep_running = False

    # ==================================================================
    # Initialisation helpers
    # ==================================================================
    def _setup_workers(self) -> None:
        self.worker = ShouterWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        self.terminal_worker = SerialTerminalWorker()
        self.terminal_thread = QThread()
        self.terminal_worker.moveToThread(self.terminal_thread)
        self.terminal_thread.start()

        self.sweep_worker = SweepWorker()
        self.sweep_thread = QThread()
        self.sweep_worker.moveToThread(self.sweep_thread)
        self.sweep_thread.start()

    def _setup_timers(self) -> None:
        self.serial_timer = QTimer()
        self.serial_timer.timeout.connect(self.terminal_worker.read_data)

        self.repeat_send_timer = QTimer()
        self.repeat_send_timer.timeout.connect(self._send_repeat_payload)

        self.fault_timer = QTimer()
        self.fault_timer.timeout.connect(self._poll_faults)

        self.arm_state_timer = QTimer()
        self.arm_state_timer.timeout.connect(self._poll_arm_state)

        self.api_operation_timeout = QTimer(self)
        self.api_operation_timeout.setSingleShot(True)
        self.api_operation_timeout.timeout.connect(self._on_api_operation_timeout)

    def _setup_panels(self) -> None:
        # Central widget (unused but required by QMainWindow)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        self.setCentralWidget(central)
        self.setDockNestingEnabled(False)

        # --- Basic Mode (left) ---
        self.basic = BasicPanel()
        self.dock_basic = QDockWidget("Basic Mode", self)
        self.dock_basic.setObjectName("dock_basic_mode")
        self.dock_basic.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.dock_basic.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_basic.setTitleBarWidget(QWidget())
        self.dock_basic.setWidget(self.basic)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_basic)

        # --- Serial Terminal (right) ---
        self.terminal = TerminalPanel()
        self.dock_terminal = QDockWidget("Serial Terminal", self)
        self.dock_terminal.setObjectName("dock_terminal_mode")
        self.dock_terminal.setAllowedAreas(Qt.RightDockWidgetArea)
        self.dock_terminal.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_terminal.setWidget(self.terminal)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_terminal)

        # --- Sweep Scan (right, tabbed) ---
        self.sweep = SweepPanel()
        self.dock_sweep = QDockWidget("Sweep Scan", self)
        self.dock_sweep.setObjectName("dock_sweep")
        self.dock_sweep.setAllowedAreas(Qt.RightDockWidgetArea)
        self.dock_sweep.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_sweep.setWidget(self.sweep)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_sweep)

        # --- Log Panel (bottom) ---
        self.log_panel = LogPanel()
        self.dock_log = QDockWidget("Log Panel", self)
        self.dock_log.setObjectName("dock_log")
        self.dock_log.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.dock_log.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_log.setWidget(self.log_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_log)

        # Arrange docks
        self.splitDockWidget(self.dock_basic, self.dock_terminal, Qt.Horizontal)
        self.tabifyDockWidget(self.dock_terminal, self.dock_sweep)
        self.dock_terminal.raise_()
        self.splitDockWidget(self.dock_basic, self.dock_log, Qt.Vertical)
        self.dock_log.raise_()

    # ==================================================================
    # Signal/slot wiring
    # ==================================================================
    def _setup_connections(self) -> None:
        bp = self.basic  # basic panel
        tp = self.terminal  # terminal panel
        sp = self.sweep  # sweep panel
        lp = self.log_panel

        # --- ChipSHOUTER connection ---
        bp.btn_connect.clicked.connect(self._connect_api)
        bp.btn_disconnect.clicked.connect(self._disconnect_api)
        bp.btn_refresh_ports.clicked.connect(bp.refresh_ports)

        # --- Configuration ---
        bp.btn_set_voltage.clicked.connect(
            lambda: self.worker.request_set_voltage.emit(bp.voltage_slider.value())
        )
        bp.btn_set_width.clicked.connect(
            lambda: self.worker.request_set_pulse_width.emit(
                bp.pulse_width_slider.value()
            )
        )
        bp.btn_set_repeat.clicked.connect(
            lambda: self.worker.request_set_pulse_repeat.emit(
                bp.pulse_repeat_slider.value()
            )
        )
        bp.btn_set_deadtime.clicked.connect(
            lambda: self.worker.request_set_deadtime.emit(bp.deadtime_slider.value())
        )
        bp.btn_apply_all.clicked.connect(self._apply_all_settings)
        bp.btn_set_hwtrig_mode.clicked.connect(
            lambda: self.worker.request_set_hwtrig_mode.emit(
                bp.hwtrig_mode_box.currentIndex() == 0
            )
        )
        bp.btn_set_hwtrig_term.clicked.connect(
            lambda: self.worker.request_set_hwtrig_term.emit(
                bp.hwtrig_term_box.currentIndex() == 0
            )
        )
        bp.btn_reset_device.clicked.connect(self.worker.request_reset.emit)

        # --- Probe tip & PW limits ---
        bp.probe_tip_box.currentTextChanged.connect(self._on_probe_changed)
        bp.voltage_slider.valueChanged.connect(
            self._on_voltage_changed_update_pw_limits
        )
        self._on_probe_changed()  # apply initial limits

        # --- Actions ---
        bp.btn_arm.clicked.connect(self._arm_device)
        bp.btn_disarm.clicked.connect(self._disarm_device)
        bp.btn_pulse.clicked.connect(self._request_pulse)
        bp.btn_mute.clicked.connect(
            lambda: self.worker.request_mute.emit(bp.btn_mute.isChecked())
        )
        bp.btn_mute.toggled.connect(self._update_mute_button_appearance)

        # --- Serial Terminal ---
        tp.btn_term_connect.clicked.connect(self._connect_terminal)
        tp.btn_term_disconnect.clicked.connect(self._disconnect_terminal)
        tp.btn_term_refresh.clicked.connect(tp.refresh_ports)
        tp.btn_send_cmd.clicked.connect(self._send_terminal_command)
        tp.terminal_input.returnPressed.connect(self._send_terminal_command)
        tp.btn_clear_term.clicked.connect(tp.terminal_output.clear)
        tp.btn_send_mode.clicked.connect(self._send_test_mode)
        tp.btn_send_signal.clicked.connect(self._send_test_signal)
        tp.btn_repeat_start.clicked.connect(self._start_repeat_send)
        tp.btn_repeat_stop.clicked.connect(self._stop_repeat_send)
        tp.btn_export_terminal_csv.clicked.connect(self._export_terminal_log_csv)

        self.terminal_worker.data_received.connect(
            self._append_terminal_data, Qt.UniqueConnection
        )
        self.terminal_worker.status_signal.connect(
            self._append_terminal_status, Qt.UniqueConnection
        )

        # --- Fault log ---
        lp.btn_read_faults.clicked.connect(
            lambda: self.worker.request_read_faults_current.emit(True)
        )
        lp.btn_read_latched.clicked.connect(
            self.worker.request_read_faults_latched.emit
        )
        lp.btn_clear_faults.clicked.connect(self.worker.request_clear_faults.emit)
        lp.btn_clear_event_log.clicked.connect(lp.log_view.clear)

        # --- Sweep ---
        sp.btn_sweep_start.clicked.connect(self._start_sweep)
        sp.btn_sweep_stop.clicked.connect(self._stop_sweep)
        sp.chk_sweep_voltage.toggled.connect(sp.update_group_visibility)
        sp.chk_sweep_pw.toggled.connect(sp.update_group_visibility)
        sp.chk_sweep_delay.toggled.connect(sp.update_group_visibility)
        sp.update_group_visibility()
        sp.btn_sweep_export.clicked.connect(self._export_sweep_csv)
        sp.btn_sweep_clear.clicked.connect(sp.sweep_results_log.clear)
        self.sweep_worker.progress_signal.connect(self._on_sweep_progress)
        self.sweep_worker.result_signal.connect(self._on_sweep_result)
        self.sweep_worker.sweep_finished.connect(self._on_sweep_finished)
        self.sweep_worker.log_signal.connect(self._on_sweep_log)

        # --- Worker -> UI ---
        self.worker.log_signal.connect(self._append_log)
        self.worker.status_signal.connect(self._update_status)
        self.worker.reset_detected.connect(self._handle_reset)
        self.worker.fault_signal.connect(self._append_fault_log)
        self.worker.connection_changed.connect(self._on_api_connection_changed)
        self.worker.armed_changed.connect(self._on_api_armed_changed)
        self.worker.busy_changed.connect(self._on_api_busy_changed)

    # ==================================================================
    # Button state management
    # ==================================================================
    def _refresh_action_buttons(self) -> None:
        bp = self.basic
        controls = self.api_connected and not self.api_busy

        bp.btn_connect.setEnabled(not self.api_connected and not self.api_busy)
        bp.btn_disconnect.setEnabled(self.api_connected and not self.api_busy)

        bp.btn_arm.setEnabled(controls and not self.api_armed)
        bp.btn_disarm.setEnabled(controls and self.api_armed)
        bp.btn_pulse.setEnabled(controls and self.api_armed)

        bp.btn_set_voltage.setEnabled(controls)
        bp.btn_set_width.setEnabled(controls)
        bp.btn_set_repeat.setEnabled(controls)
        bp.btn_set_deadtime.setEnabled(controls)
        bp.btn_set_hwtrig_mode.setEnabled(controls)
        bp.btn_set_hwtrig_term.setEnabled(controls)
        bp.btn_reset_device.setEnabled(controls)
        bp.btn_apply_all.setEnabled(controls)

    # ==================================================================
    # API connection (ChipSHOUTER)
    # ==================================================================
    def _connect_api(self) -> None:
        port = self.basic.port_box.currentText()
        if self.api_busy:
            self._append_log("Sistema ocupado, espere...")
            return
        if self.terminal_connected and self.terminal_port == port:
            self._append_log(
                f"Error: Puerto {port} ya está en uso por Serial Terminal. Desconecte primero."
            )
            return
        self.pending_api_action = "connect"
        self.api_operation_timeout.start(API_OPERATION_TIMEOUT_MS)
        self.worker.request_connect.emit(port)

    def _disconnect_api(self) -> None:
        if self.api_busy:
            self._append_log("Sistema ocupado, espere...")
            return
        self.pending_api_action = "disconnect"
        self.api_operation_timeout.start(API_OPERATION_TIMEOUT_MS)
        self.worker.request_disconnect.emit()

    def _on_api_connection_changed(self, connected: bool, port: str) -> None:
        self.api_connected = connected
        self.api_port = port if connected else None
        if connected:
            self.fault_timer.start(FAULT_POLL_INTERVAL_MS)
            self.arm_state_timer.start(ARM_STATE_POLL_INTERVAL_MS)
        else:
            self.fault_timer.stop()
            self.arm_state_timer.stop()
            self.api_armed = False
        self._update_ui_mutex_state()
        self._refresh_action_buttons()

    def _on_api_armed_changed(self, armed: bool) -> None:
        self.api_armed = armed
        bp = self.basic
        if armed:
            bp.btn_arm.setStyleSheet(
                "QPushButton {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 3px solid #ffff00;}"
                "QPushButton:disabled {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 3px solid #ffff00;}"
            )
            bp.btn_disarm.setStyleSheet(
                "background-color: #00c853; color: black; font-weight: 900; "
                "font-size: 14px; border: 2px solid #69f0ae;"
            )
        else:
            bp.btn_arm.setStyleSheet(
                "QPushButton {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 2px solid #ff8a80;}"
                "QPushButton:disabled {background-color: #c62828; color: white; font-weight: 900; "
                "font-size: 14px; border: 2px solid #ff8a80;}"
            )
            bp.btn_disarm.setStyleSheet(
                "background-color: #1b5e20; color: white; font-weight: 900; "
                "font-size: 14px; border: 2px solid #66bb6a;"
            )
        self._refresh_action_buttons()

    def _on_api_busy_changed(self, busy: bool) -> None:
        self.api_busy = busy
        if not busy and self.pending_api_action:
            self.pending_api_action = None
            self.api_operation_timeout.stop()
        self._refresh_action_buttons()

    def _on_api_operation_timeout(self) -> None:
        if self.pending_api_action:
            self._append_log(f"Timeout en operación API: {self.pending_api_action}")
            self.pending_api_action = None
            self.api_busy = False
            self._refresh_action_buttons()

    def _update_ui_mutex_state(self) -> None:
        """Update tooltips based on connection states to prevent port conflicts."""
        tp = self.terminal
        bp = self.basic

        if self.api_connected and self.api_port:
            if tp.term_port_box.currentText() == self.api_port:
                tp.btn_term_connect.setToolTip(
                    f"Puerto {self.api_port} en uso por ChipSHOUTER API"
                )
            else:
                tp.btn_term_connect.setToolTip("")
        else:
            tp.btn_term_connect.setToolTip("")

        if self.terminal_connected and self.terminal_port:
            if bp.port_box.currentText() == self.terminal_port:
                bp.btn_connect.setToolTip(
                    f"Puerto {self.terminal_port} en uso por Serial Terminal"
                )
            else:
                bp.btn_connect.setToolTip("")
        else:
            bp.btn_connect.setToolTip("")

    # ==================================================================
    # Actions
    # ==================================================================
    def _apply_all_settings(self) -> None:
        bp = self.basic
        self.worker.request_set_voltage.emit(bp.voltage_slider.value())
        self.worker.request_set_pulse_width.emit(bp.pulse_width_slider.value())
        self.worker.request_set_pulse_repeat.emit(bp.pulse_repeat_slider.value())
        self.worker.request_set_deadtime.emit(bp.deadtime_slider.value())
        self.worker.request_set_hwtrig_mode.emit(bp.hwtrig_mode_box.currentIndex() == 0)
        self.worker.request_set_hwtrig_term.emit(bp.hwtrig_term_box.currentIndex() == 0)

    def _arm_device(self) -> None:
        if not self.api_connected or self.api_busy:
            return
        self.worker.request_arm.emit(True)

    def _disarm_device(self) -> None:
        if not self.api_connected or self.api_busy:
            return
        self.worker.request_arm.emit(False)

    def _request_pulse(self) -> None:
        if not self.api_connected or self.api_busy:
            return
        self.worker.request_fire.emit()

    @staticmethod
    def _update_mute_button_appearance(muted: bool) -> None:
        # Text stays the same regardless of state (as in original)
        pass

    # ==================================================================
    # Serial terminal
    # ==================================================================
    def _connect_terminal(self) -> None:
        tp = self.terminal
        port = tp.term_port_box.currentText()

        if self.api_connected and self.api_port == port:
            self._append_terminal_status(
                f"Error: Puerto {port} ya está en uso por ChipSHOUTER API. Desconecte primero."
            )
            return

        self.serial_timer.stop()
        if self.terminal_worker.is_connected:
            self.terminal_worker.disconnect_serial()

        baudrate = int(tp.baud_box.currentText())
        self.terminal_worker.connect_serial(port, baudrate)

        if self.terminal_worker.is_connected:
            self.terminal_connected = True
            self.terminal_port = port
            self.serial_timer.start(SERIAL_POLL_INTERVAL_MS)
            self._update_ui_mutex_state()

    def _disconnect_terminal(self) -> None:
        self.serial_timer.stop()
        self._stop_repeat_send()
        self.terminal_worker.disconnect_serial()
        self.terminal_connected = False
        self.terminal_port = None
        self._update_ui_mutex_state()

    def _send_terminal_command(self) -> None:
        cmd = self.terminal.terminal_input.text().strip()
        if cmd:
            self.terminal.terminal_input.clear()
            self.terminal_worker.send_data(cmd)

    def _send_test_mode(self) -> None:
        if not self.terminal_worker.is_connected:
            self._append_terminal_status("Error: Terminal no conectado")
            return
        mode = self.terminal.test_mode_box.currentText()
        self.terminal_worker.send_data(f"MODE:{mode}")

    def _send_test_signal(self) -> None:
        if not self.terminal_worker.is_connected:
            self._append_terminal_status("Error: Terminal no conectado")
            return
        self.terminal_worker.send_data("START")

    def _start_repeat_send(self) -> None:
        tp = self.terminal
        if not self.terminal_worker.is_connected:
            self._append_terminal_status("Error: Terminal no conectado")
            return
        payload = tp.repeat_payload_input.text().strip()
        if not payload:
            self._append_terminal_status("Error: contenido vacío para envío repetido")
            return
        interval = tp.repeat_interval_spin.value()
        self.repeat_send_timer.start(interval)
        tp.btn_repeat_start.setEnabled(False)
        tp.btn_repeat_stop.setEnabled(True)
        self._append_terminal_status(
            f"Repeat TX iniciado: '{payload}' cada {interval} ms"
        )

    def _stop_repeat_send(self) -> None:
        tp = self.terminal
        was_running = self.repeat_send_timer.isActive()
        self.repeat_send_timer.stop()
        tp.btn_repeat_start.setEnabled(True)
        tp.btn_repeat_stop.setEnabled(False)
        if was_running:
            self._append_terminal_status("Repeat TX detenido")

    def _send_repeat_payload(self) -> None:
        if not self.terminal_worker.is_connected:
            self._stop_repeat_send()
            self._append_terminal_status("Repeat TX detenido: terminal desconectado")
            return
        payload = self.terminal.repeat_payload_input.text().strip()
        if not payload:
            self._stop_repeat_send()
            self._append_terminal_status("Repeat TX detenido: contenido vacío")
            return
        self.terminal_worker.send_data(payload)

    def _append_terminal_data(self, data: str) -> None:
        now = time.time()
        if data == self.last_terminal_data and (now - self.last_terminal_time) < 0.5:
            return
        self.last_terminal_data = data
        self.last_terminal_time = now

        out = self.terminal.terminal_output
        out.moveCursor(QTextCursor.End)
        out.insertPlainText(data)
        if not data.endswith("\n"):
            out.insertPlainText("\n")
        out.moveCursor(QTextCursor.End)

    def _append_terminal_status(self, status: str) -> None:
        self.terminal.terminal_output.append(
            f"[{time.strftime('%H:%M:%S')}] {status}\n"
        )
        self._append_log(status)

    # ==================================================================
    # Logging
    # ==================================================================
    def _update_status(self, status: str) -> None:
        self.setWindowTitle(f"{APP_TITLE} - {status}")

    def _append_log(self, text: str) -> None:
        timestamp = f"[{time.strftime('%H:%M:%S')}] {text}"
        self.log_panel.log_view.append(timestamp)
        if text.startswith("RX:"):
            self.terminal.terminal_output.append(text)

    def _poll_faults(self) -> None:
        if self.api_connected:
            self.worker.request_read_faults_current.emit(False)

    def _poll_arm_state(self) -> None:
        if self.api_connected:
            self.worker.request_read_arm_state.emit()

    def _append_fault_log(self, text: str) -> None:
        ts = time.strftime("%H:%M:%S")
        if "[CURRENT]" in text and "No faults" not in text and "Error" not in text:
            color = "red"
        elif "[LATCHED]" in text and "No latched" not in text and "Error" not in text:
            color = "#cc6600"
        elif "Error" in text:
            color = "darkred"
        else:
            color = "green"
        view = self.log_panel.log_view
        view.append(f"<span style='color:{color};'>[{ts}] {text}</span>")
        view.moveCursor(QTextCursor.End)

    def _handle_reset(self) -> None:
        self.api_armed = False
        self._refresh_action_buttons()
        self._append_log("!!! RESET DETECTADO !!! Re-iniciando en 5s...")
        self._append_fault_log("[INFO] !!! HARDWARE RESET DETECTED !!!")

    # ==================================================================
    # Probe-tip / PW-limit logic
    # ==================================================================
    def _get_pw_limits_for_voltage(self, voltage: int, probe: str | None = None):
        if probe is None:
            probe = self.basic.probe_tip_box.currentText()
        info = PROBE_LIMITS.get(probe, PROBE_LIMITS["4mm"])
        table = info["table"]
        v = max(table[0][0], min(table[-1][0], voltage))
        for i in range(len(table) - 1):
            v0, pw_min0, pw_max0 = table[i]
            v1, pw_min1, pw_max1 = table[i + 1]
            if v0 <= v <= v1:
                if v1 == v0:
                    return pw_min0, pw_max0
                t = (v - v0) / (v1 - v0)
                pw_min = int(round(pw_min0 + t * (pw_min1 - pw_min0)))
                pw_max = int(round(pw_max0 + t * (pw_max1 - pw_max0)))
                return pw_min, pw_max
        return table[-1][1], table[-1][2]

    def _on_probe_changed(self) -> None:
        bp = self.basic
        sp = self.sweep
        probe = bp.probe_tip_box.currentText()
        info = PROBE_LIMITS.get(probe, PROBE_LIMITS["4mm"])
        v_min, v_max = info["v_min"], info["v_max"]

        bp.voltage_slider.setRange(v_min, v_max)
        cur_v = bp.voltage_slider.value()
        if cur_v < v_min:
            bp.voltage_slider.setValue(v_min)
        elif cur_v > v_max:
            bp.voltage_slider.setValue(v_max)

        sp.sweep_v_start_slider.setRange(v_min, v_max)
        sp.sweep_v_end_slider.setRange(v_min, v_max)
        if sp.sweep_v_start_slider.value() < v_min:
            sp.sweep_v_start_slider.setValue(v_min)
        if sp.sweep_v_end_slider.value() > v_max:
            sp.sweep_v_end_slider.setValue(v_max)

        self._on_voltage_changed_update_pw_limits(bp.voltage_slider.value())

    def _on_voltage_changed_update_pw_limits(self, voltage: int | None = None) -> None:
        bp = self.basic
        sp = self.sweep
        if voltage is None:
            voltage = bp.voltage_slider.value()

        pw_min, pw_max = self._get_pw_limits_for_voltage(voltage)

        bp.pulse_width_slider.setRange(pw_min, pw_max)
        cur = bp.pulse_width_slider.value()
        if cur < pw_min:
            bp.pulse_width_slider.setValue(pw_min)
        elif cur > pw_max:
            bp.pulse_width_slider.setValue(pw_max)
        bp.pulse_width_edit.setText(str(bp.pulse_width_slider.value()))

        probe = bp.probe_tip_box.currentText()
        info = PROBE_LIMITS.get(probe, PROBE_LIMITS["4mm"])
        global_pw_min = min(row[1] for row in info["table"])
        global_pw_max = max(row[2] for row in info["table"])
        sp.sweep_pw_start_slider.setRange(global_pw_min, global_pw_max)
        sp.sweep_pw_end_slider.setRange(global_pw_min, global_pw_max)
        if sp.sweep_pw_start_slider.value() < global_pw_min:
            sp.sweep_pw_start_slider.setValue(global_pw_min)
        if sp.sweep_pw_end_slider.value() > global_pw_max:
            sp.sweep_pw_end_slider.setValue(global_pw_max)

        bp.pw_limits_label.setText(f"PW: {pw_min}\u2013{pw_max} ns @ {voltage}V")

    # ==================================================================
    # CSV export
    # ==================================================================
    def _export_terminal_log_csv(self) -> None:
        log_text = self.terminal.terminal_output.toPlainText().strip()
        if not log_text:
            self._append_log("No hay datos para exportar (terminal_log)")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Terminal Log to CSV",
            default_filename("terminal_log"),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return
        try:
            export_raw_lines_to_csv(log_text, file_path)
            self._append_log(f"Terminal log exportado a CSV: {file_path}")
        except Exception as e:
            self._append_log(f"Error exportando terminal CSV: {e}")

    def _export_sweep_csv(self) -> None:
        results = self.sweep_worker.results
        if not results:
            self._append_log("No sweep data to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sweep Results",
            default_filename("sweep_results"),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return
        try:
            export_sweep_results_to_csv(results, file_path)
            self._append_log(f"Sweep CSV exported: {file_path}")
        except Exception as e:
            self._append_log(f"Error exporting sweep CSV: {e}")

    # ==================================================================
    # Sweep
    # ==================================================================
    def _start_sweep(self) -> None:
        if not self.api_connected:
            self._append_log("Error: ChipSHOUTER not connected. Connect first.")
            return
        if not self.terminal_connected or not self.terminal_worker.is_connected:
            self._append_log(
                "Error: Serial Terminal must be connected to the target board first."
            )
            return
        if self.sweep_running:
            return
        if not self.worker.cs:
            self._append_log("Error: No ChipSHOUTER device available.")
            return

        self.fault_timer.stop()
        self.arm_state_timer.stop()
        self.serial_timer.stop()
        self._stop_repeat_send()

        self.sweep_running = True
        sp = self.sweep
        sp.btn_sweep_start.setEnabled(False)
        sp.btn_sweep_stop.setEnabled(True)
        sp.sweep_results_log.clear()
        sp.sweep_progress.setValue(0)

        config = sp.get_config()

        # Calculate total points for progress bar
        axes = config["sweep_axes"]
        v_count = (
            len(range(config["v_start"], config["v_end"] + 1, max(1, config["v_step"])))
            if "voltage" in axes
            else 1
        )
        pw_count = (
            len(
                range(
                    config["pw_start"], config["pw_end"] + 1, max(1, config["pw_step"])
                )
            )
            if "pulse_width" in axes
            else 1
        )
        delays = list(
            range(
                config["delay_start"],
                config["delay_end"] + 1,
                max(1, config["delay_step"]),
            )
        )
        d_count = max(1, len(delays)) if "delay" in axes else 1
        sp.sweep_progress.setMaximum(v_count * pw_count * d_count)

        self._append_log(
            f"Sweep started: V[{config['v_start']}-{config['v_end']}] "
            f"PW[{config['pw_start']}-{config['pw_end']}] "
            f"Delay[{config['delay_start']}-{config['delay_end']}us]"
        )

        self.sweep_worker._start_requested.emit(
            self.worker.cs, self.terminal_worker.serial_port, config
        )

    def _stop_sweep(self) -> None:
        self.sweep_worker.stop_sweep()
        self.sweep.sweep_status_label.setText("Stopping...")

    def _on_sweep_progress(self, current: int, total: int, info: str) -> None:
        self.sweep.sweep_progress.setValue(current)
        self.sweep.sweep_status_label.setText(info)

    def _on_sweep_result(self, result: dict) -> None:
        v = result["voltage"]
        pw = result["pulse_width"]
        d = result.get("delay_us", 0)
        g = result["glitches"]
        r = result.get("resets", 0)
        e = result["errors"]
        n = result["normal"]
        rate = result["rate"]
        if g > 0:
            color, marker = "#ff5252", "*** GLITCH ***"
        elif r > 0:
            color, marker = "#ff6e40", "RESET"
        elif e > 0:
            color, marker = "#ffab40", "ERROR"
        else:
            color, marker = "#69f0ae", "OK"
        self.sweep.sweep_results_log.append(
            f"<span style='color:{color};'>V={v:>3}V  PW={pw:>3}ns  D={d:>3}\u00b5s  "
            f"G:{g} R:{r} E:{e} N:{n}  Rate:{rate}  [{marker}]</span>"
        )

    def _on_sweep_finished(self, summary: str) -> None:
        self.sweep_running = False
        sp = self.sweep
        sp.btn_sweep_start.setEnabled(True)
        sp.btn_sweep_stop.setEnabled(False)
        sp.sweep_status_label.setText(summary)
        self._append_log(f"Sweep: {summary}")

        if self.api_connected:
            self.fault_timer.start(FAULT_POLL_INTERVAL_MS)
            self.arm_state_timer.start(ARM_STATE_POLL_INTERVAL_MS)
        if self.terminal_connected and self.terminal_worker.is_connected:
            self.serial_timer.start(SERIAL_POLL_INTERVAL_MS)

    def _on_sweep_log(self, text: str) -> None:
        self.sweep.sweep_results_log.append(
            f"<span style='color:#888;'>[LOG] {text}</span>"
        )
        self._append_log(f"[Sweep] {text}")

    # ==================================================================
    # Cleanup
    # ==================================================================
    def closeEvent(self, event) -> None:
        if self.sweep_running:
            self.sweep_worker.stop_sweep()
        self.sweep_thread.quit()
        self.sweep_thread.wait()

        self.serial_timer.stop()
        self.repeat_send_timer.stop()
        self.fault_timer.stop()
        self.arm_state_timer.stop()

        self.terminal_worker.disconnect_serial()
        self.terminal_thread.quit()
        self.terminal_thread.wait()

        self.worker.disconnect_device()
        self.worker_thread.quit()
        self.worker_thread.wait()

        event.accept()
