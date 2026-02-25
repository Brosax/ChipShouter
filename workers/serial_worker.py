"""
SerialTerminalWorker – QObject running on a dedicated QThread.

Manages a raw serial connection to a target board (e.g. KW45).
Provides connect/disconnect, send, and poll-based read functionality.
"""

import serial
from PySide6.QtCore import QObject, Signal

from config import SERIAL_READ_TIMEOUT


class SerialTerminalWorker(QObject):
    data_received = Signal(str)
    status_signal = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.serial_port: serial.Serial | None = None
        self.is_connected = False
        self.running = False
        self.last_sent_command = ""
        self.is_reading = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect_serial(self, port: str, baudrate: int) -> None:
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=SERIAL_READ_TIMEOUT,
            )
            self.is_connected = True
            self.running = True
            self.is_reading = False
            self.status_signal.emit(f"Terminal conectado a {port} @ {baudrate} baud")
        except Exception as e:
            self.status_signal.emit(f"Error de conexión: {e}")

    def disconnect_serial(self) -> None:
        self.running = False
        self.is_reading = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.serial_port = None
        self.status_signal.emit("Terminal desconectado")

    # ------------------------------------------------------------------
    # Data I/O
    # ------------------------------------------------------------------
    def send_data(self, data: str) -> None:
        if self.is_connected and self.serial_port:
            try:
                self.last_sent_command = data
                self.serial_port.write((data + "\r\n").encode())
                self.data_received.emit(f"> {data}\n")
            except Exception as e:
                self.status_signal.emit(f"Error TX: {e}")

    def read_data(self) -> None:
        """Called periodically by a QTimer on the main thread."""
        if self.is_reading:
            return
        if (
            not self.is_connected
            or not self.serial_port
            or not self.serial_port.is_open
        ):
            return

        self.is_reading = True
        try:
            if self.serial_port.in_waiting:
                data = self.serial_port.read(self.serial_port.in_waiting).decode(
                    errors="ignore"
                )
                if data and data.strip():
                    self.data_received.emit(data)
        except Exception:
            pass
        finally:
            self.is_reading = False
