import sys
import time
import serial
import serial.tools.list_ports
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QSlider, QLabel, QTextEdit, QComboBox,
                             QTabWidget, QSpinBox, QGroupBox, QGridLayout, QLineEdit,
                             QPlainTextEdit, QSplitter, QFrame)
from PySide6.QtCore import QThread, Signal, QObject, Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
from chipshouter import ChipSHOUTER
from chipshouter.com_tools import Reset_Exception


# --- Custom Exception for Stop Request ---
class StopExecution(Exception):
    """Exception raised when user requests to stop code execution"""
    pass


# --- Code Execution Worker (runs in separate thread) ---
class CodeExecutionWorker(QObject):
    output_signal = Signal(str)
    finished_signal = Signal()
    error_signal = Signal(str)
    start_execution = Signal()  # Signal to trigger execution

    def __init__(self):
        super().__init__()
        self.cs = None
        self.code = ""
        self.stop_requested = False
        # Connect the start signal to run_code slot
        self.start_execution.connect(self.run_code)

    def set_context(self, cs, code):
        self.cs = cs
        self.code = code
        self.stop_requested = False

    def request_stop(self):
        self.stop_requested = True

    def check_stop(self):
        """Check if stop was requested, raise StopExecution if so"""
        if self.stop_requested:
            raise StopExecution("Ejecución detenida por el usuario")

    def run_code(self):
        if self.cs is None:
            self.error_signal.emit("Error: Dispositivo no conectado")
            self.finished_signal.emit()
            return

        # Redirect stdout to capture print statements
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        class OutputCapture:
            def __init__(self, signal):
                self.signal = signal
            def write(self, text):
                if text.strip():
                    self.signal.emit(text.rstrip())
            def flush(self):
                pass

        sys.stdout = OutputCapture(self.output_signal)
        sys.stderr = OutputCapture(self.error_signal)

        try:
            # Create a local namespace with the device and check_stop function
            local_ns = {
                'cs': self.cs, 
                'time': time, 
                'Reset_Exception': Reset_Exception,
                'StopExecution': StopExecution,
                'check_stop': self.check_stop  # Inject check_stop function
            }
            
            # Execute code directly - user should call check_stop() in their loops
            exec(self.code, local_ns)
            self.output_signal.emit("--- Código ejecutado correctamente ---")
        except StopExecution as e:
            self.output_signal.emit(f"--- {str(e)} ---")
        except Reset_Exception:
            self.error_signal.emit("!!! RESET DETECTADO !!!")
        except Exception as e:
            self.error_signal.emit(f"Error de ejecución: {str(e)}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.finished_signal.emit()

# --- 工作线程：负责所有串口通信 (Hilo de trabajo) ---
class ShouterWorker(QObject):
    log_signal = Signal(str)
    status_signal = Signal(str)
    reset_detected = Signal()

    def __init__(self):
        super().__init__()
        self.cs = None
        self.is_connected = False

    def connect_device(self, port):
        try:
            self.cs = ChipSHOUTER(port)
            self.is_connected = True
            self.log_signal.emit(f"Conectado a {port}")
        except Exception as e:
            self.log_signal.emit(f"Error de conexión: {str(e)}")

    def disconnect_device(self):
        if self.is_connected and self.cs:
            try:
                self.cs.armed = 0  # Disarm before disconnect
                self.cs = None
                self.is_connected = False
                self.status_signal.emit("DESCONECTADO")
                self.log_signal.emit("Dispositivo desconectado")
            except Exception as e:
                self.log_signal.emit(f"Error al desconectar: {str(e)}")

    def arm_device(self, should_arm):
        if not self.is_connected: return
        try:
            self.cs.armed = 1 if should_arm else 0
            state = "ARMADO (PELIGRO)" if should_arm else "DESARMADO"
            self.status_signal.emit(state)
            self.log_signal.emit(f"Estado cambiado: {state}")
        except Reset_Exception:
            self.reset_detected.emit()

    def fire_pulse(self):
        if not self.is_connected: return
        try:
            self.cs.pulse = 1
            self.log_signal.emit("¡Pulso disparado!")
        except Reset_Exception:
            self.reset_detected.emit()

    def toggle_mute(self, mute_enabled):
        if not self.is_connected: return
        try:
            self.cs.mute = 1 if mute_enabled else 0
            state = "SILENCIADO" if mute_enabled else "SONIDO HABILITADO"
            self.log_signal.emit(f"Estado de sonido: {state}")
        except Reset_Exception:
            self.reset_detected.emit()

    def set_voltage(self, voltage):
        if not self.is_connected: return
        try:
            self.cs.voltage = voltage
            self.log_signal.emit(f"Voltaje configurado: {voltage}V")
        except Reset_Exception:
            self.reset_detected.emit()

    def set_pulse_width(self, width):
        if not self.is_connected: return
        try:
            self.cs.pulse.width = width
            self.log_signal.emit(f"Ancho de pulso configurado: {width}ns")
        except Reset_Exception:
            self.reset_detected.emit()

    def set_pulse_repeat(self, repeat):
        if not self.is_connected: return
        try:
            self.cs.pulse.repeat = repeat
            self.log_signal.emit(f"Repeticiones configuradas: {repeat}")
        except Reset_Exception:
            self.reset_detected.emit()

    def set_deadtime(self, deadtime):
        if not self.is_connected: return
        try:
            self.cs.pulse.deadtime = deadtime
            self.log_signal.emit(f"Deadtime configurado: {deadtime}ms")
        except Reset_Exception:
            self.reset_detected.emit()

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
            self.reset_detected.emit()
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
        self.terminal_connected = False
        self.api_port = None
        self.terminal_port = None

        # 初始化线程 (Inicializar hilo)
        self.worker = ShouterWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # Code execution worker
        self.code_worker = CodeExecutionWorker()
        self.code_thread = QThread()
        self.code_worker.moveToThread(self.code_thread)
        self.code_thread.start()

        # Serial terminal worker
        self.terminal_worker = SerialTerminalWorker()
        self.terminal_thread = QThread()
        self.terminal_worker.moveToThread(self.terminal_thread)
        self.terminal_thread.start()

        # Timer for reading serial data
        self.serial_timer = QTimer()
        self.serial_timer.timeout.connect(self.terminal_worker.read_data)

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 串口选择 (Conexión) - Common for both modes
        conn_group = QGroupBox("ChipSHOUTER Connection")
        conn_layout = QHBoxLayout(conn_group)
        self.port_box = QComboBox()
        self.refresh_ports()
        self.btn_refresh_ports = QPushButton("⟳")
        self.btn_refresh_ports.setFixedWidth(30)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setStyleSheet("background-color: #aaffaa;")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setStyleSheet("background-color: #ffddaa;")
        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.btn_refresh_ports)
        conn_layout.addWidget(self.port_box)
        conn_layout.addWidget(self.btn_connect)
        conn_layout.addWidget(self.btn_disconnect)
        main_layout.addWidget(conn_group)

        # Tab Widget for Basic/Expert modes
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # ========== BASIC MODE TAB ==========
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)

        # Configuration Group
        config_group = QGroupBox("Device Configuration")
        config_grid = QGridLayout(config_group)

        # Voltage
        config_grid.addWidget(QLabel("Voltage (V):"), 0, 0)
        self.voltage_spin = QSpinBox()
        self.voltage_spin.setRange(150, 500)
        self.voltage_spin.setValue(300)
        self.voltage_spin.setSuffix(" V")
        config_grid.addWidget(self.voltage_spin, 0, 1)
        self.btn_set_voltage = QPushButton("Set")
        config_grid.addWidget(self.btn_set_voltage, 0, 2)

        # Pulse Width
        config_grid.addWidget(QLabel("Pulse Width (ns):"), 1, 0)
        self.pulse_width_spin = QSpinBox()
        self.pulse_width_spin.setRange(10, 500)
        self.pulse_width_spin.setValue(160)
        self.pulse_width_spin.setSuffix(" ns")
        config_grid.addWidget(self.pulse_width_spin, 1, 1)
        self.btn_set_width = QPushButton("Set")
        config_grid.addWidget(self.btn_set_width, 1, 2)

        # Pulse Repeat
        config_grid.addWidget(QLabel("Pulse Repeat:"), 2, 0)
        self.pulse_repeat_spin = QSpinBox()
        self.pulse_repeat_spin.setRange(1, 100)
        self.pulse_repeat_spin.setValue(10)
        config_grid.addWidget(self.pulse_repeat_spin, 2, 1)
        self.btn_set_repeat = QPushButton("Set")
        config_grid.addWidget(self.btn_set_repeat, 2, 2)

        # Deadtime
        config_grid.addWidget(QLabel("Deadtime (ms):"), 3, 0)
        self.deadtime_spin = QSpinBox()
        self.deadtime_spin.setRange(1, 1000)
        self.deadtime_spin.setValue(10)
        self.deadtime_spin.setSuffix(" ms")
        config_grid.addWidget(self.deadtime_spin, 3, 1)
        self.btn_set_deadtime = QPushButton("Set")
        config_grid.addWidget(self.btn_set_deadtime, 3, 2)

        # Apply All button
        self.btn_apply_all = QPushButton("Apply All Settings")
        self.btn_apply_all.setStyleSheet("background-color: #aaddff;")
        config_grid.addWidget(self.btn_apply_all, 4, 0, 1, 3)

        basic_layout.addWidget(config_group)

        # Action Buttons
        action_group = QGroupBox("Actions")
        action_layout = QHBoxLayout(action_group)
        self.btn_arm = QPushButton("ARM DEVICE")
        self.btn_arm.setStyleSheet("background-color: #ffcccc;")
        self.btn_arm.setFixedHeight(50)
        self.btn_disarm = QPushButton("DISARM")
        self.btn_disarm.setStyleSheet("background-color: #aaffaa; font-weight: bold;")
        self.btn_disarm.setFixedHeight(50)
        self.btn_disarm.setEnabled(False)  # Start in disarmed state
        self.btn_pulse = QPushButton("PULSE")
        self.btn_pulse.setStyleSheet("background-color: #ffaaaa; font-weight: bold;")
        self.btn_pulse.setFixedHeight(50)
        self.btn_pulse.setEnabled(False)  # Can't pulse when disarmed
        self.btn_mute = QPushButton("MUTE SOUND")
        self.btn_mute.setCheckable(True)
        self.btn_mute.setFixedHeight(50)
        action_layout.addWidget(self.btn_arm)
        action_layout.addWidget(self.btn_disarm)
        action_layout.addWidget(self.btn_pulse)
        action_layout.addWidget(self.btn_mute)
        basic_layout.addWidget(action_group)

        # Log for basic mode
        self.log_view_basic = QTextEdit()
        self.log_view_basic.setReadOnly(True)
        self.log_view_basic.setMaximumHeight(150)
        basic_layout.addWidget(QLabel("Event Log:"))
        basic_layout.addWidget(self.log_view_basic)

        self.tab_widget.addTab(basic_tab, "Basic Mode")

        # ========== EXPERT MODE TAB ==========
        expert_tab = QWidget()
        expert_layout = QVBoxLayout(expert_tab)

        # Code Editor Section
        code_header = QHBoxLayout()
        code_header.addWidget(QLabel("Python Code Editor (use 'cs' for device):"))
        self.btn_run_code = QPushButton("Run Code")
        self.btn_run_code.setStyleSheet("background-color: #aaffaa;")
        self.btn_stop_code = QPushButton("Stop")
        self.btn_stop_code.setStyleSheet("background-color: #ffaaaa;")
        self.btn_clear_code = QPushButton("Clear")
        code_header.addWidget(self.btn_run_code)
        code_header.addWidget(self.btn_stop_code)
        code_header.addWidget(self.btn_clear_code)
        expert_layout.addLayout(code_header)

        self.code_editor = QPlainTextEdit()
        self.code_editor.setFont(QFont("Consolas", 10))
        self.code_editor.setPlainText(
'''# Example code - ChipSHOUTER Control
# Use check_stop() in loops to allow safe stopping from GUI

def setup_device():
    cs.voltage = 300            # Ajuste de voltaje 
    cs.pulse.width = 160        # Ancho de pulso (ns) 
    cs.pulse.repeat = 10        # Número de repeticiones a nivel de hardware
    cs.pulse.deadtime = 10      # Deadtime (ms)

    intervalo = (cs.pulse.repeat * cs.pulse.deadtime)/1000.0

    cs.mute = 1                 # Silenciar el zumbador interno 
    
    cs.armed = 1 
    time.sleep(1)
    print("Dispositivo armado, iniciando pulsos continuos...")
    return intervalo

intervalo = setup_device()

try:
    count = 0
    while True:
        check_stop()  # <-- Call this to allow GUI stop button to work
        
        cs.pulse = 1        # Enviar un pulso de inyección 
        count += 1
        print("recuentos -> ", count)

        time.sleep(intervalo)    # Intervalo de retardo 
        
except Reset_Exception:
    print("Device rebooted!")
    time.sleep(5)
    setup_device()
except StopExecution:
    print("Detenido por el usuario...")
finally:
    cs.armed = 0
    print("Dispositivo desarmado.")
'''
        )
        expert_layout.addWidget(self.code_editor)

        # Expert mode log
        self.log_view_expert = QTextEdit()
        self.log_view_expert.setReadOnly(True)
        self.log_view_expert.setMaximumHeight(150)
        expert_layout.addWidget(QLabel("Execution Log:"))
        expert_layout.addWidget(self.log_view_expert)

        self.tab_widget.addTab(expert_tab, "Expert Mode")

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
        self.btn_term_connect.setStyleSheet("background-color: #aaffaa;")
        self.btn_term_disconnect = QPushButton("Disconnect")
        self.btn_term_disconnect.setStyleSheet("background-color: #ffddaa;")
        term_conn_layout.addWidget(self.btn_term_connect)
        term_conn_layout.addWidget(self.btn_term_disconnect)
        terminal_layout.addWidget(term_conn_group)

        # Terminal output
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
        self.btn_send_cmd.setStyleSheet("background-color: #aaddff;")
        self.btn_clear_term = QPushButton("Clear")
        cmd_layout.addWidget(self.terminal_input)
        cmd_layout.addWidget(self.btn_send_cmd)
        cmd_layout.addWidget(self.btn_clear_term)
        terminal_layout.addLayout(cmd_layout)

        self.tab_widget.addTab(terminal_tab, "Serial Terminal")

    def setup_connections(self):
        # Connection buttons - ChipSHOUTER (with UI mutex)
        self.btn_connect.clicked.connect(self.connect_api)
        self.btn_disconnect.clicked.connect(self.disconnect_api)
        self.btn_refresh_ports.clicked.connect(self.refresh_ports)

        # Basic mode - Configuration
        self.btn_set_voltage.clicked.connect(lambda: self.worker.set_voltage(self.voltage_spin.value()))
        self.btn_set_width.clicked.connect(lambda: self.worker.set_pulse_width(self.pulse_width_spin.value()))
        self.btn_set_repeat.clicked.connect(lambda: self.worker.set_pulse_repeat(self.pulse_repeat_spin.value()))
        self.btn_set_deadtime.clicked.connect(lambda: self.worker.set_deadtime(self.deadtime_spin.value()))
        self.btn_apply_all.clicked.connect(self.apply_all_settings)

        # Basic mode - Actions
        self.btn_arm.clicked.connect(self.arm_device)
        self.btn_disarm.clicked.connect(self.disarm_device)
        self.btn_pulse.clicked.connect(self.worker.fire_pulse)
        self.btn_mute.clicked.connect(lambda: self.worker.toggle_mute(self.btn_mute.isChecked()))

        # Expert mode - Code editor
        self.btn_run_code.clicked.connect(self.run_expert_code)
        self.btn_stop_code.clicked.connect(self.stop_expert_code)
        self.btn_clear_code.clicked.connect(self.code_editor.clear)

        # Code execution worker signals
        self.code_worker.output_signal.connect(self.append_code_output)
        self.code_worker.error_signal.connect(self.append_code_error)
        self.code_worker.finished_signal.connect(self.on_code_finished)

        # Expert mode - Serial Terminal
        self.btn_term_connect.clicked.connect(self.connect_terminal)
        self.btn_term_disconnect.clicked.connect(self.disconnect_terminal)
        self.btn_term_refresh.clicked.connect(self.refresh_terminal_ports)
        self.btn_send_cmd.clicked.connect(self.send_terminal_command)
        self.terminal_input.returnPressed.connect(self.send_terminal_command)
        self.btn_clear_term.clicked.connect(self.terminal_output.clear)

        # Terminal worker signals (use UniqueConnection to prevent duplicates)
        self.terminal_worker.data_received.connect(self.append_terminal_data, Qt.UniqueConnection)
        self.terminal_worker.status_signal.connect(self.append_terminal_status, Qt.UniqueConnection)

        # ChipSHOUTER Worker signals
        self.worker.log_signal.connect(self.append_log)
        self.worker.status_signal.connect(self.update_status)
        self.worker.reset_detected.connect(self.handle_reset)

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
        self.terminal_worker.disconnect_serial()
        self.terminal_connected = False
        self.terminal_port = None
        self.update_ui_mutex_state()

    def connect_api(self):
        port = self.port_box.currentText()
        
        # UI Mutex: Check if this port is already used by Serial Terminal
        if self.terminal_connected and self.terminal_port == port:
            self.append_log(f"Error: Puerto {port} ya está en uso por Serial Terminal. Desconecte primero.")
            return
        
        self.worker.connect_device(port)
        # Check if connection succeeded
        if self.worker.is_connected:
            self.api_connected = True
            self.api_port = port
            self.update_ui_mutex_state()

    def disconnect_api(self):
        self.worker.disconnect_device()
        self.api_connected = False
        self.api_port = None
        self.update_ui_mutex_state()

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
        self.worker.set_voltage(self.voltage_spin.value())
        self.worker.set_pulse_width(self.pulse_width_spin.value())
        self.worker.set_pulse_repeat(self.pulse_repeat_spin.value())
        self.worker.set_deadtime(self.deadtime_spin.value())

    def arm_device(self):
        self.worker.arm_device(True)
        # Update button styles to show armed state
        self.btn_arm.setStyleSheet("background-color: #ff6666; font-weight: bold;")
        self.btn_arm.setEnabled(False)
        self.btn_disarm.setStyleSheet("background-color: #aaffaa;")
        self.btn_disarm.setEnabled(True)
        self.btn_pulse.setEnabled(True)

    def disarm_device(self):
        self.worker.arm_device(False)
        # Update button styles to show disarmed state
        self.btn_arm.setStyleSheet("background-color: #ffcccc;")
        self.btn_arm.setEnabled(True)
        self.btn_disarm.setStyleSheet("background-color: #aaffaa; font-weight: bold;")
        self.btn_disarm.setEnabled(False)
        self.btn_pulse.setEnabled(False)

    def run_expert_code(self):
        code = self.code_editor.toPlainText()
        if code.strip():
            if not self.worker.is_connected:
                self.append_code_error("Error: Dispositivo no conectado")
                return
            # Disable run button, enable stop
            self.btn_run_code.setEnabled(False)
            self.btn_stop_code.setEnabled(True)
            self.log_view_expert.append(f"[{time.strftime('%H:%M:%S')}] --- Iniciando ejecución ---")
            # Set context and emit signal to run in worker thread
            self.code_worker.set_context(self.worker.cs, code)
            self.code_worker.start_execution.emit()

    def stop_expert_code(self):
        self.code_worker.request_stop()
        self.log_view_expert.append(f"[{time.strftime('%H:%M:%S')}] --- Solicitando detención ---")

    def on_code_finished(self):
        self.btn_run_code.setEnabled(True)
        self.btn_stop_code.setEnabled(False)
        self.log_view_expert.append(f"[{time.strftime('%H:%M:%S')}] --- Ejecución finalizada ---")

    def append_code_output(self, text):
        self.log_view_expert.append(f"[{time.strftime('%H:%M:%S')}] {text}")
        # Auto-scroll to bottom
        self.log_view_expert.moveCursor(QTextCursor.End)

    def append_code_error(self, text):
        self.log_view_expert.append(f"[{time.strftime('%H:%M:%S')}] <span style='color: red;'>{text}</span>")
        self.log_view_expert.moveCursor(QTextCursor.End)

    def send_terminal_command(self):
        cmd = self.terminal_input.text().strip()
        if cmd:
            self.terminal_input.clear()
            self.terminal_worker.send_data(cmd)

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
        # Append to both logs
        self.log_view_basic.append(timestamp)
        self.log_view_expert.append(timestamp)
        # Also to terminal if it's a RX message
        if text.startswith("RX:"):
            self.terminal_output.append(text)

    def handle_reset(self):
        self.append_log("!!! RESET DETECTADO !!! Re-iniciando en 5s...")

    def closeEvent(self, event):
        # Stop code execution
        self.code_worker.request_stop()
        self.code_thread.quit()
        self.code_thread.wait(1000)
        # Stop serial timer
        self.serial_timer.stop()
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