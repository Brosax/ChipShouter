"""
LogPanel – Unified event + fault log with fault-read controls.
"""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogPanel(QWidget):
    """Bottom dock content: event log + fault controls."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with fault buttons
        header = QHBoxLayout()
        header.addWidget(QLabel("Logs:"))

        self.btn_read_faults = QPushButton("Read Current")
        self.btn_read_faults.setFixedHeight(24)
        self.btn_read_latched = QPushButton("Read Latched")
        self.btn_read_latched.setFixedHeight(24)
        self.btn_clear_faults = QPushButton("Clear Faults")
        self.btn_clear_faults.setFixedHeight(24)
        self.btn_clear_faults.setStyleSheet("background-color: #bf360c; color: white;")
        self.btn_clear_event_log = QPushButton("Clear")
        self.btn_clear_event_log.setFixedHeight(24)

        header.addWidget(self.btn_read_faults)
        header.addWidget(self.btn_read_latched)
        header.addWidget(self.btn_clear_faults)
        header.addWidget(self.btn_clear_event_log)
        header.addStretch()
        layout.addLayout(header)

        # Log text area
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #252526; color: #eee;")
        layout.addWidget(self.log_view)
