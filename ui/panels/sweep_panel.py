"""
SweepPanel – Parameter-sweep configuration, progress, results log,
and export controls.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from config import (
    SWEEP_DELAY_END,
    SWEEP_DELAY_RANGE,
    SWEEP_DELAY_START,
    SWEEP_DELAY_STEP,
    SWEEP_DEADTIME,
    SWEEP_PW_END,
    SWEEP_PW_SLIDER_MAX,
    SWEEP_PW_SLIDER_MIN,
    SWEEP_PW_START,
    SWEEP_PW_STEP,
    SWEEP_PULSE_INTERVAL,
    SWEEP_PULSE_REPEAT,
    SWEEP_PULSES_PER_POINT,
    SWEEP_V_END,
    SWEEP_V_START,
    SWEEP_V_STEP,
    VOLTAGE_RANGE,
)
from ui.panels.basic_panel import _sync_edit_to_slider


class SweepPanel(QWidget):
    """Right-hand dock content (tabbed with terminal): sweep scan."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._build_info(layout)
        self._build_axis_checkboxes(layout)
        self._build_voltage_sweep(layout)
        self._build_pw_sweep(layout)
        self._build_delay_sweep(layout)
        self._build_test_params(layout)
        self._build_controls(layout)
        self._build_results(layout)

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------
    def _build_info(self, parent: QVBoxLayout) -> None:
        lbl = QLabel(
            "\u26a1 Uses Serial Terminal connection to target board (ext HW trigger)"
        )
        lbl.setStyleSheet("color: #ffab40; font-weight: bold; padding: 4px;")
        parent.addWidget(lbl)

    def _build_axis_checkboxes(self, parent: QVBoxLayout) -> None:
        group = QGroupBox("Sweep Axes")
        h = QHBoxLayout(group)

        self.chk_sweep_voltage = QCheckBox("Voltage")
        self.chk_sweep_voltage.setChecked(True)
        self.chk_sweep_voltage.setStyleSheet("font-weight: bold; color: #4fc3f7;")

        self.chk_sweep_pw = QCheckBox("Pulse Width")
        self.chk_sweep_pw.setChecked(True)
        self.chk_sweep_pw.setStyleSheet("font-weight: bold; color: #81c784;")

        self.chk_sweep_delay = QCheckBox("Delay")
        self.chk_sweep_delay.setChecked(False)
        self.chk_sweep_delay.setStyleSheet("font-weight: bold; color: #ffb74d;")

        h.addWidget(self.chk_sweep_voltage)
        h.addWidget(self.chk_sweep_pw)
        h.addWidget(self.chk_sweep_delay)
        h.addStretch()
        parent.addWidget(group)

    def _build_voltage_sweep(self, parent: QVBoxLayout) -> None:
        self.sv_group = QGroupBox("Voltage Sweep (V)")
        g = QGridLayout(self.sv_group)

        self.sweep_v_start_slider, self.sweep_v_start_edit = self._slider_row(
            g, 0, "Start:", VOLTAGE_RANGE, SWEEP_V_START
        )
        self.sweep_v_end_slider, self.sweep_v_end_edit = self._slider_row(
            g, 1, "End:", VOLTAGE_RANGE, SWEEP_V_END
        )

        g.addWidget(QLabel("Step:"), 2, 0)
        self.sweep_v_step = QSpinBox()
        self.sweep_v_step.setRange(1, 350)
        self.sweep_v_step.setValue(SWEEP_V_STEP)
        self.sweep_v_step.setSuffix(" V")
        g.addWidget(self.sweep_v_step, 2, 1)

        parent.addWidget(self.sv_group)

    def _build_pw_sweep(self, parent: QVBoxLayout) -> None:
        self.sp_group = QGroupBox("Pulse Width Sweep (ns)")
        g = QGridLayout(self.sp_group)

        self.sweep_pw_start_slider, self.sweep_pw_start_edit = self._slider_row(
            g, 0, "Start:", (SWEEP_PW_SLIDER_MIN, SWEEP_PW_SLIDER_MAX), SWEEP_PW_START
        )
        self.sweep_pw_end_slider, self.sweep_pw_end_edit = self._slider_row(
            g, 1, "End:", (SWEEP_PW_SLIDER_MIN, SWEEP_PW_SLIDER_MAX), SWEEP_PW_END
        )

        g.addWidget(QLabel("Step:"), 2, 0)
        self.sweep_pw_step = QSpinBox()
        self.sweep_pw_step.setRange(1, 880)
        self.sweep_pw_step.setValue(SWEEP_PW_STEP)
        self.sweep_pw_step.setSuffix(" ns")
        g.addWidget(self.sweep_pw_step, 2, 1)

        parent.addWidget(self.sp_group)

    def _build_delay_sweep(self, parent: QVBoxLayout) -> None:
        self.sd_group = QGroupBox("Trigger Delay Sweep (\u00b5s)")
        g = QGridLayout(self.sd_group)

        g.addWidget(QLabel("Start:"), 0, 0)
        self.sweep_delay_start = QSpinBox()
        self.sweep_delay_start.setRange(*SWEEP_DELAY_RANGE)
        self.sweep_delay_start.setValue(SWEEP_DELAY_START)
        self.sweep_delay_start.setSuffix(" \u00b5s")
        g.addWidget(self.sweep_delay_start, 0, 1)

        g.addWidget(QLabel("End:"), 0, 2)
        self.sweep_delay_end = QSpinBox()
        self.sweep_delay_end.setRange(*SWEEP_DELAY_RANGE)
        self.sweep_delay_end.setValue(SWEEP_DELAY_END)
        self.sweep_delay_end.setSuffix(" \u00b5s")
        g.addWidget(self.sweep_delay_end, 0, 3)

        g.addWidget(QLabel("Step:"), 0, 4)
        self.sweep_delay_step = QSpinBox()
        self.sweep_delay_step.setRange(1, 125)
        self.sweep_delay_step.setValue(SWEEP_DELAY_STEP)
        self.sweep_delay_step.setSuffix(" \u00b5s")
        g.addWidget(self.sweep_delay_step, 0, 5)

        parent.addWidget(self.sd_group)

    def _build_test_params(self, parent: QVBoxLayout) -> None:
        group = QGroupBox("Test Parameters")
        g = QGridLayout(group)

        g.addWidget(QLabel("Pulses/Point:"), 0, 0)
        self.sweep_pulses = QSpinBox()
        self.sweep_pulses.setRange(1, 1000)
        self.sweep_pulses.setValue(SWEEP_PULSES_PER_POINT)
        g.addWidget(self.sweep_pulses, 0, 1)

        g.addWidget(QLabel("Pulse Repeat:"), 0, 2)
        self.sweep_repeat = QSpinBox()
        self.sweep_repeat.setRange(1, 10000)
        self.sweep_repeat.setValue(SWEEP_PULSE_REPEAT)
        g.addWidget(self.sweep_repeat, 0, 3)

        g.addWidget(QLabel("Pulse Interval (s):"), 0, 4)
        self.sweep_pulse_interval = QSpinBox()
        self.sweep_pulse_interval.setRange(0, 60)
        self.sweep_pulse_interval.setValue(SWEEP_PULSE_INTERVAL)
        self.sweep_pulse_interval.setSuffix(" s")
        self.sweep_pulse_interval.setToolTip(
            "Delay between each pulse within a test point (seconds)"
        )
        g.addWidget(self.sweep_pulse_interval, 0, 5)

        g.addWidget(QLabel("Deadtime (ms):"), 1, 0)
        self.sweep_deadtime = QSpinBox()
        self.sweep_deadtime.setRange(1, 1000)
        self.sweep_deadtime.setValue(SWEEP_DEADTIME)
        self.sweep_deadtime.setSuffix(" ms")
        g.addWidget(self.sweep_deadtime, 1, 1)

        g.addWidget(QLabel("Target Mode:"), 1, 2)
        self.sweep_mode_box = QComboBox()
        self.sweep_mode_box.addItems(["1", "2", "3", "4"])
        self.sweep_mode_box.setCurrentText("1")
        g.addWidget(self.sweep_mode_box, 1, 3)

        parent.addWidget(group)

    def _build_controls(self, parent: QVBoxLayout) -> None:
        h = QHBoxLayout()

        self.btn_sweep_start = QPushButton("\u25b6 Start Sweep")
        self.btn_sweep_start.setStyleSheet(
            "background-color: #00695c; color: white; font-weight: bold; font-size: 14px;"
        )
        self.btn_sweep_start.setFixedHeight(40)

        self.btn_sweep_stop = QPushButton("\u25a0 Stop")
        self.btn_sweep_stop.setStyleSheet(
            "background-color: #b71c1c; color: white; font-weight: bold; font-size: 14px;"
        )
        self.btn_sweep_stop.setFixedHeight(40)
        self.btn_sweep_stop.setEnabled(False)

        h.addWidget(self.btn_sweep_start)
        h.addWidget(self.btn_sweep_stop)
        parent.addLayout(h)

        self.sweep_progress = QProgressBar()
        self.sweep_progress.setValue(0)
        self.sweep_progress.setFormat("%v / %m  (%p%)")
        parent.addWidget(self.sweep_progress)

        self.sweep_status_label = QLabel("Ready")
        self.sweep_status_label.setStyleSheet("color: #aaa;")
        parent.addWidget(self.sweep_status_label)

    def _build_results(self, parent: QVBoxLayout) -> None:
        self.sweep_results_log = QTextEdit()
        self.sweep_results_log.setReadOnly(True)
        self.sweep_results_log.setFont(QFont("Consolas", 9))
        self.sweep_results_log.setStyleSheet(
            "background-color: #1e1e1e; color: #00ff00;"
        )
        parent.addWidget(self.sweep_results_log)

        h = QHBoxLayout()
        self.btn_sweep_export = QPushButton("Export Sweep CSV")
        self.btn_sweep_export.setStyleSheet("background-color: #1565c0; color: white;")
        self.btn_sweep_clear = QPushButton("Clear")
        h.addWidget(self.btn_sweep_export)
        h.addWidget(self.btn_sweep_clear)
        h.addStretch()
        parent.addLayout(h)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _slider_row(
        grid: QGridLayout, row: int, label: str, range_: tuple[int, int], default: int
    ):
        """Add Start/End slider row and return (slider, edit)."""
        grid.addWidget(QLabel(label), row, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(*range_)
        slider.setValue(default)
        grid.addWidget(slider, row, 1)

        edit = QLineEdit(str(default))
        edit.setFixedWidth(60)
        edit.setAlignment(Qt.AlignCenter)
        grid.addWidget(edit, row, 2)

        slider.valueChanged.connect(lambda v, e=edit: e.setText(str(v)))
        edit.editingFinished.connect(
            lambda s=slider, e=edit: _sync_edit_to_slider(e, s)
        )

        return slider, edit

    def get_sweep_axes(self) -> set[str]:
        """Return set of active sweep axes based on checkboxes."""
        axes: set[str] = set()
        if self.chk_sweep_voltage.isChecked():
            axes.add("voltage")
        if self.chk_sweep_pw.isChecked():
            axes.add("pulse_width")
        if self.chk_sweep_delay.isChecked():
            axes.add("delay")
        return axes

    def get_config(self) -> dict:
        """Collect all sweep configuration values into a dict."""
        return {
            "v_start": self.sweep_v_start_slider.value(),
            "v_end": self.sweep_v_end_slider.value(),
            "v_step": self.sweep_v_step.value(),
            "pw_start": self.sweep_pw_start_slider.value(),
            "pw_end": self.sweep_pw_end_slider.value(),
            "pw_step": self.sweep_pw_step.value(),
            "delay_start": self.sweep_delay_start.value(),
            "delay_end": self.sweep_delay_end.value(),
            "delay_step": self.sweep_delay_step.value(),
            "pulses_per_point": self.sweep_pulses.value(),
            "pulse_repeat": self.sweep_repeat.value(),
            "deadtime": self.sweep_deadtime.value(),
            "pulse_interval": self.sweep_pulse_interval.value(),
            "mode": self.sweep_mode_box.currentText(),
            "sweep_axes": self.get_sweep_axes(),
        }

    def update_group_visibility(self) -> None:
        """Enable/disable parameter groups based on checkbox state."""
        self.sv_group.setEnabled(self.chk_sweep_voltage.isChecked())
        self.sp_group.setEnabled(self.chk_sweep_pw.isChecked())
        self.sd_group.setEnabled(self.chk_sweep_delay.isChecked())
