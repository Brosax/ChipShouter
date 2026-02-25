"""
BasicPanel – ChipSHOUTER connection, device configuration, and action buttons.

This is a self-contained QWidget that builds its own layout and exposes
its interactive widgets as public attributes so the MainWindow can wire
signals.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from config import (
    DEFAULT_DEADTIME,
    DEFAULT_PULSE_REPEAT,
    DEFAULT_PULSE_WIDTH,
    DEFAULT_VOLTAGE,
    DEADTIME_RANGE,
    PULSE_REPEAT_RANGE,
    PULSE_WIDTH_RANGE,
    VOLTAGE_RANGE,
)
from utils.serial_utils import refresh_port_combobox


class BasicPanel(QWidget):
    """Left-hand dock content: connection + config + actions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._build_connection_group(layout)
        self._build_config_group(layout)
        self._build_action_group(layout)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def _build_connection_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("ChipSHOUTER Connection")
        h = QHBoxLayout(group)

        self.port_box = QComboBox()
        refresh_port_combobox(self.port_box)

        self.btn_refresh_ports = QPushButton("\u27f3")  # ⟳
        self.btn_refresh_ports.setFixedWidth(30)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setStyleSheet("background-color: #1b5e20; color: white;")

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setStyleSheet("background-color: #bf360c; color: white;")

        h.addWidget(QLabel("Port:"))
        h.addWidget(self.btn_refresh_ports)
        h.addWidget(self.port_box)
        h.addWidget(self.btn_connect)
        h.addWidget(self.btn_disconnect)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Device configuration
    # ------------------------------------------------------------------
    def _build_config_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Device Configuration")
        grid = QGridLayout(group)

        # Row 0 – Probe Tip
        grid.addWidget(QLabel("Probe Tip:"), 0, 0)
        self.probe_tip_box = QComboBox()
        self.probe_tip_box.addItems(["4mm", "1mm"])
        self.probe_tip_box.setCurrentText("4mm")
        self.probe_tip_box.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.probe_tip_box, 0, 1)
        self.pw_limits_label = QLabel("")
        self.pw_limits_label.setStyleSheet("color: #ffab40; font-size: 11px;")
        grid.addWidget(self.pw_limits_label, 0, 2, 1, 2)

        # Row 1 – Voltage
        self.voltage_slider, self.voltage_edit, self.btn_set_voltage = (
            self._add_slider_row(
                grid, 1, "Voltage (V):", VOLTAGE_RANGE, DEFAULT_VOLTAGE
            )
        )

        # Row 2 – Pulse Width
        self.pulse_width_slider, self.pulse_width_edit, self.btn_set_width = (
            self._add_slider_row(
                grid, 2, "Pulse Width (ns):", PULSE_WIDTH_RANGE, DEFAULT_PULSE_WIDTH
            )
        )

        # Row 3 – Pulse Repeat
        self.pulse_repeat_slider, self.pulse_repeat_edit, self.btn_set_repeat = (
            self._add_slider_row(
                grid, 3, "Pulse Repeat:", PULSE_REPEAT_RANGE, DEFAULT_PULSE_REPEAT
            )
        )

        # Row 4 – Deadtime
        self.deadtime_slider, self.deadtime_edit, self.btn_set_deadtime = (
            self._add_slider_row(
                grid, 4, "Deadtime (ms):", DEADTIME_RANGE, DEFAULT_DEADTIME
            )
        )

        # Row 5 – HW Trigger Mode
        grid.addWidget(QLabel("HW Trigger Mode:"), 5, 0)
        self.hwtrig_mode_box = QComboBox()
        self.hwtrig_mode_box.addItems(["Active-High", "Active-Low"])
        grid.addWidget(self.hwtrig_mode_box, 5, 1)
        self.btn_set_hwtrig_mode = QPushButton("Set")
        grid.addWidget(self.btn_set_hwtrig_mode, 5, 2)

        # Row 6 – HW Trigger Termination
        grid.addWidget(QLabel("HW Trigger Term:"), 6, 0)
        self.hwtrig_term_box = QComboBox()
        self.hwtrig_term_box.addItems(["High Impedance (~1.8K)", "50-ohm"])
        grid.addWidget(self.hwtrig_term_box, 6, 1)
        self.btn_set_hwtrig_term = QPushButton("Set")
        grid.addWidget(self.btn_set_hwtrig_term, 6, 2)

        # Row 7 – Reset
        self.btn_reset_device = QPushButton("Reset Device")
        self.btn_reset_device.setStyleSheet("background-color: #b71c1c; color: white;")
        grid.addWidget(self.btn_reset_device, 7, 0, 1, 3)

        # Row 8 – Apply All
        self.btn_apply_all = QPushButton("Apply All Settings")
        self.btn_apply_all.setStyleSheet("background-color: #01579b; color: white;")
        grid.addWidget(self.btn_apply_all, 8, 0, 1, 3)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Action buttons
    # ------------------------------------------------------------------
    def _build_action_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Actions")
        h = QHBoxLayout(group)

        self.btn_arm = QPushButton("ARM")
        self.btn_arm.setStyleSheet(
            "QPushButton {background-color: #c62828; color: white; font-weight: 900; "
            "font-size: 14px; border: 2px solid #ff8a80;}"
            "QPushButton:disabled {background-color: #c62828; color: white; font-weight: 900; "
            "font-size: 14px; border: 2px solid #ff8a80;}"
        )
        self.btn_arm.setFixedHeight(50)

        self.btn_disarm = QPushButton("DISARM")
        self.btn_disarm.setStyleSheet(
            "background-color: #1b5e20; font-weight: 900; color: white; "
            "border: 1px solid #66bb6a;"
        )
        self.btn_disarm.setFixedHeight(50)
        self.btn_disarm.setEnabled(False)

        self.btn_pulse = QPushButton("PULSE")
        self.btn_pulse.setStyleSheet(
            "background-color: #e64a19; font-weight: bold; color: white;"
        )
        self.btn_pulse.setFixedHeight(50)
        self.btn_pulse.setEnabled(False)

        self.btn_mute = QPushButton("MUTE SOUND")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedHeight(50)
        self.btn_mute.setStyleSheet(
            "QPushButton {background-color: #37474f; color: white;}"
            "QPushButton:checked {background-color: #ffb300; color: black; font-weight: bold;}"
        )

        h.addWidget(self.btn_arm)
        h.addWidget(self.btn_disarm)
        h.addWidget(self.btn_pulse)
        h.addWidget(self.btn_mute)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _add_slider_row(
        grid: QGridLayout, row: int, label: str, range_: tuple[int, int], default: int
    ):
        """Add a label + slider + line-edit + Set button row and return them."""
        grid.addWidget(QLabel(label), row, 0)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(*range_)
        slider.setValue(default)
        grid.addWidget(slider, row, 1)

        edit = QLineEdit(str(default))
        edit.setFixedWidth(80)
        edit.setAlignment(Qt.AlignCenter)
        grid.addWidget(edit, row, 2)

        # Keep slider <-> edit in sync
        slider.valueChanged.connect(lambda v, e=edit: e.setText(str(v)))
        edit.editingFinished.connect(
            lambda s=slider, e=edit: _sync_edit_to_slider(e, s)
        )

        btn = QPushButton("Set")
        grid.addWidget(btn, row, 3)

        return slider, edit, btn

    def refresh_ports(self) -> None:
        """Refresh the ChipSHOUTER port combo box."""
        refresh_port_combobox(self.port_box)


def _sync_edit_to_slider(edit: QLineEdit, slider: QSlider) -> None:
    """Sync a QLineEdit value back to its paired QSlider, clamping to range."""
    try:
        val = int(edit.text())
        val = max(slider.minimum(), min(slider.maximum(), val))
        slider.setValue(val)
    except ValueError:
        edit.setText(str(slider.value()))
