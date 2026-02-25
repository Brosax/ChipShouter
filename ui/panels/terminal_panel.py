"""
TerminalPanel – Serial terminal connection, output, command input,
and repeat-send controls.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFont

from config import (
    BAUD_RATES,
    DEFAULT_BAUD,
    REPEAT_SEND_DEFAULT_INTERVAL,
    REPEAT_SEND_DEFAULT_PAYLOAD,
    REPEAT_SEND_INTERVAL_RANGE,
)
from utils.serial_utils import refresh_port_combobox


class TerminalPanel(QWidget):
    """Right-hand dock content: serial terminal."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._build_connection(layout)
        self._build_quick_controls(layout)
        self._build_log_area(layout)
        self._build_command_input(layout)
        self._build_repeat_send(layout)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def _build_connection(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Serial Connection")
        h = QHBoxLayout(group)

        h.addWidget(QLabel("Port:"))
        self.term_port_box = QComboBox()
        refresh_port_combobox(self.term_port_box)
        self.term_port_box.setMinimumWidth(100)
        h.addWidget(self.term_port_box)

        self.btn_term_refresh = QPushButton("\u27f3")
        self.btn_term_refresh.setFixedWidth(30)
        h.addWidget(self.btn_term_refresh)

        h.addWidget(QLabel("Baud:"))
        self.baud_box = QComboBox()
        self.baud_box.addItems(BAUD_RATES)
        self.baud_box.setCurrentText(DEFAULT_BAUD)
        h.addWidget(self.baud_box)
        h.addStretch()

        self.btn_term_connect = QPushButton("Connect")
        self.btn_term_connect.setStyleSheet("background-color: #1b5e20; color: white;")
        self.btn_term_disconnect = QPushButton("Disconnect")
        self.btn_term_disconnect.setStyleSheet(
            "background-color: #bf360c; color: white;"
        )
        h.addWidget(self.btn_term_connect)
        h.addWidget(self.btn_term_disconnect)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Quick test-board controls
    # ------------------------------------------------------------------
    def _build_quick_controls(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Test Board Quick Control")
        h = QHBoxLayout(group)

        h.addWidget(QLabel("Mode:"))
        self.test_mode_box = QComboBox()
        self.test_mode_box.addItems(["1", "2", "3", "4"])
        self.test_mode_box.setCurrentText("1")
        h.addWidget(self.test_mode_box)

        self.btn_send_mode = QPushButton("Send MODE")
        self.btn_send_mode.setStyleSheet("background-color: #1565c0; color: white;")
        h.addWidget(self.btn_send_mode)

        self.btn_send_signal = QPushButton("Send START Signal")
        self.btn_send_signal.setStyleSheet(
            "background-color: #2e7d32; color: white; font-weight: bold;"
        )
        h.addWidget(self.btn_send_signal)
        h.addStretch()

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Terminal log area
    # ------------------------------------------------------------------
    def _build_log_area(self, parent_layout: QVBoxLayout) -> None:
        header = QHBoxLayout()
        header.addWidget(QLabel("Terminal Log:"))

        self.btn_export_terminal_csv = QPushButton("Export CSV")
        self.btn_export_terminal_csv.setStyleSheet(
            "background-color: #1565c0; color: white;"
        )
        self.btn_export_terminal_csv.setFixedHeight(24)
        header.addWidget(self.btn_export_terminal_csv)
        header.addStretch()

        parent_layout.addLayout(header)

        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Consolas", 10))
        self.terminal_output.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        parent_layout.addWidget(self.terminal_output)

    # ------------------------------------------------------------------
    # Command input
    # ------------------------------------------------------------------
    def _build_command_input(self, parent_layout: QVBoxLayout) -> None:
        h = QHBoxLayout()

        self.terminal_input = QLineEdit()
        self.terminal_input.setFont(QFont("Consolas", 10))
        self.terminal_input.setPlaceholderText(
            "Enter command and press Enter or Send..."
        )

        self.btn_send_cmd = QPushButton("Send")
        self.btn_send_cmd.setStyleSheet("background-color: #01579b; color: white;")
        self.btn_clear_term = QPushButton("Clear")

        h.addWidget(self.terminal_input)
        h.addWidget(self.btn_send_cmd)
        h.addWidget(self.btn_clear_term)

        parent_layout.addLayout(h)

    # ------------------------------------------------------------------
    # Repeat send
    # ------------------------------------------------------------------
    def _build_repeat_send(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Repeat Send")
        grid = QGridLayout(group)

        grid.addWidget(QLabel("Content:"), 0, 0)
        self.repeat_payload_input = QLineEdit()
        self.repeat_payload_input.setPlaceholderText("e.g. START or MODE:1")
        self.repeat_payload_input.setText(REPEAT_SEND_DEFAULT_PAYLOAD)
        grid.addWidget(self.repeat_payload_input, 0, 1, 1, 3)

        grid.addWidget(QLabel("Interval:"), 1, 0)
        self.repeat_interval_spin = QSpinBox()
        self.repeat_interval_spin.setRange(*REPEAT_SEND_INTERVAL_RANGE)
        self.repeat_interval_spin.setValue(REPEAT_SEND_DEFAULT_INTERVAL)
        self.repeat_interval_spin.setSuffix(" ms")
        grid.addWidget(self.repeat_interval_spin, 1, 1)

        self.btn_repeat_start = QPushButton("Start Repeat")
        self.btn_repeat_start.setStyleSheet("background-color: #6a1b9a; color: white;")
        self.btn_repeat_stop = QPushButton("Stop")
        self.btn_repeat_stop.setStyleSheet("background-color: #424242; color: white;")
        self.btn_repeat_stop.setEnabled(False)
        grid.addWidget(self.btn_repeat_start, 1, 2)
        grid.addWidget(self.btn_repeat_stop, 1, 3)

        parent_layout.addWidget(group)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def refresh_ports(self) -> None:
        refresh_port_combobox(self.term_port_box)
