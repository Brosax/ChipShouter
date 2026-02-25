"""
Serial port utility functions.

Pure helper functions with no dependency on business logic or UI.
"""

import serial.tools.list_ports


def list_serial_ports() -> list[str]:
    """Return a list of available serial port device names."""
    return [port.device for port in serial.tools.list_ports.comports()]


def refresh_port_combobox(combo_box) -> None:
    """Refresh a QComboBox with available serial ports, preserving selection."""
    current = combo_box.currentText()
    combo_box.clear()
    ports = list_serial_ports()
    if ports:
        combo_box.addItems(ports)
        if current in ports:
            combo_box.setCurrentText(current)
    else:
        combo_box.addItems(["No ports found"])
