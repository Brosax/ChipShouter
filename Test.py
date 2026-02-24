import serial
import time
import sys

# --- CONFIGURACIÓN ---
SERIAL_PORT = 'COM8'  # Asegúrate de que este es el puerto correcto
BAUD_RATE = 115200
TIMEOUT = 2  # Aumentamos un poco el timeout por seguridad

# Diccionario de Errores SSS (Status Codes)
SSS_STATUS = {
    "0x5A5A5A5A": "SUCCESS",
    "0x3C3C3C3C": "FAIL",
    "0x3C3C0001": "INVALID_ARGUMENT",
    "0x5A5A0002": "RESOURCE_BUSY",
    "0x3C3C0000": "INTERNAL_OP_ERROR"
}

def wait_for_ready(ser):
    """
    Lee la salida inicial del microcontrolador hasta que el menú esté listo.
    Esto limpia el buffer de mensajes de arranque.
    """
    print("⏳ Esperando a la placa KW45...")
    start_time = time.time()
    while (time.time() - start_time) < 3.0: # Esperar máx 3 segundos al inicio
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"[BOOT] {line}")
        if "Commands:" in line: # La señal de que el main() llegó al bucle while(1)
            print("✅ Placa sincronizada y lista.\n")
            return True
    print("⚠️ No se detectó el mensaje de inicio (¿ya estaba encendida?). Continuando...")
    return False

def set_mode(ser, mode):
    """Envía el comando de modo y espera la confirmación (ACK)."""
    cmd = f"MODE:{mode}\n"
    ser.write(cmd.encode())
    print(f"➡️ Enviando comando: {cmd.strip()}")
    
    # Esperamos el ACK
    start = time.time()
    while (time.time() - start) < 1.0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if f"ACK:MODE:{mode}" in line:
            print(f"✅ Modo {mode} confirmado por hardware.")
            return True
    print("❌ Error: No se recibió ACK del modo.")
    return False

def run_attack_cycle(ser):
    """Envía START y parsea la respuesta completa."""
    ser.reset_input_buffer() # Limpiar basura anterior importante
    ser.write(b"START\n")
    
    data = {}
    collecting = False
    
    while True:
        try:
            # Leemos línea por línea
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            # 1. Detectar inicio de bloque
            if "--- DATA_START ---" in line:
                collecting = True
                continue
            
            # 2. Detectar fin de bloque
            if "--- DATA_END ---" in line:
                return data # Retornamos el diccionario completo
            
            # 3. Detectar Errores
            if "ERROR:" in line:
                parts = line.split(":")
                err_hex = parts[-1] if len(parts) > 1 else "UNKNOWN"
                err_msg = SSS_STATUS.get(err_hex, "UNKNOWN_ERROR")
                print(f"🚨 FALLO EN CHIP: {err_msg} ({line})")
                return None

            # 4. Recolectar datos (KEY, PT, CT)
            if collecting and ":" in line:
                # El formato es "ETIQUETA:VALORHEX"
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key, value = parts
                    data[key.strip()] = value.strip()
            
            # Timeout de seguridad dentro del bucle
            if not line and collecting: 
                # Si estamos recolectando y deja de llegar info...
                break

        except Exception as e:
            print(f"Error de parsing: {e}")
            break
            
    return None

# --- MAIN LOOP ---
if __name__ == "__main__":
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
    except serial.SerialException as e:
        print(f"❌ No se pudo abrir el puerto {SERIAL_PORT}: {e}")
        sys.exit(1)

    try:
        # 1. Sincronización inicial
        wait_for_ready(ser)

        # 2. Configurar el Modo deseado (ej. Modo 4 para aleatoriedad total)
        # Modo 1: Fijo / Fijo
        # Modo 2: Random Key / Fijo PT
        # Modo 3: Fijo Key / Random PT
        # Modo 4: Random Key / Random PT
        if not set_mode(ser, 1): # Cambia el número aquí según tu test
            print("No se pudo configurar el modo. Abortando.")
            sys.exit(1)

        print("\n🚀 Iniciando Inyección de Fallos / Captura de Trazas...\n")
        
        previous_ct = None
        counter = 0

        while True:
            # Ejecutar un ciclo de encriptación
            result = run_attack_cycle(ser)
            
            if result:
                current_ct = result.get('CT', '')
                current_pt = result.get('PT', '')
                current_key = result.get('KEY', '')

                # Mostrar datos (simplificado)
                print(f"[{counter}] KEY: {current_key[:8]}... | PT: {current_pt[:8]}... | CT: {current_ct}")

                # Lógica de detección de fallos (DFA)
                # Si el PT y la KEY son iguales que antes, pero el CT cambió -> ¡FAULT!
                if previous_ct and current_ct != previous_ct:
                    # NOTA: Esto solo vale para Modos donde PT/KEY sean fijos (Modo 1)
                    # Si usas Modo 4, el CT siempre cambiará.
                    print(f"\n🔥🔥🔥 GLITCH EXITOSO DETECTADO 🔥🔥🔥")
                    print(f"Esperado: {previous_ct}")
                    print(f"Obtenido: {current_ct}")
                    # break # Descomenta para detenerte al encontrar un glitch

                previous_ct = current_ct
                counter += 1
            else:
                # Si result es None, hubo un error o timeout
                pass

            # Pequeña pausa para no saturar si usas un debugger
            # time.sleep(0.01) 

    except KeyboardInterrupt:
        print("\n🛑 Detenido por el usuario.")
    finally:
        ser.close()
        print("Puerto cerrado.")