import serial
import time

SSS_STATUS = {
    "0x5A5A5A5A": "SUCCESS",
    "0x3C3C3C3C": "FAIL",
    "0x3C3C0001": "INVALID_ARGUMENT",
    "0x5A5A0002": "RESOURCE_BUSY",
    "0x3C3C0000": "INTERNAL_OP_ERROR"
}

# Configura el puerto COM de tu KW45 (ej. 'COM3' o '/dev/ttyACM0')
ser = serial.Serial('COM8', 115200, timeout=1)

#def send_command(cmd):
#    ser.write((cmd + '\n').encode())
#    return ser.readline().decode().strip()
def send_command(command):
    command_bytes = (command + '\n').encode('utf-8')
    try:
        ser.write(command_bytes)
    except serial.SerialException as e:
        print(f"Error de comunicación: {e}") 

# Configurar Modo 4 (Variable Key / Variable PT)
send_command("MODE:1")

def trigger_and_read():
    send_command("START")
    collecting = False
    data = {}
    
    while True:
        line = ser.readline().decode().strip()
        if "--- DATA_START ---" in line:
            collecting = True

            continue
        if "--- DATA_END ---" in line:
            print(f"Clave detectada: {data['KEY']}")
            print(f"Texto Cifrado:  {data['CT']}")
            print(f"Texto Plano:  {data['PT']}\n")
            break
        
        if collecting and ":" in line:
            key, value = line.split(":", 1)
            data[key] = value
            
        if "ERROR:" in line:
            # Extraemos el código de error para mostrarlo
            print(f"⚠️ [PLACA] Error detectado: {line}")
            
            # Opcional: Si el error es crítico, podrías decidir cerrar el script o reintentar
            #if "0x3C3C0000" in line:
            #    print("   Sugerencia: Reinicia la placa o revisa la sesión del Enclave.")

            err_code = line.split(":")[-1].strip()
            significado = SSS_STATUS.get(err_code, "UNKNOWN_ERROR")
            print(f"🚨 Error en KW45: {significado} ({err_code})")
                        
            break # Saltamos al siguiente ciclo para no intentar procesar esto como datos


    return data

# Ejemplo de uso: enviar START continuamente
previous_data = None
try:
    while True:
        current_data = trigger_and_read()
        
        if previous_data is not None and current_data:
            if current_data != previous_data:
                print("\n¡Cambio detectado en los resultados! Deteniendo el bucle.")
                print(f"Anterior: {previous_data}")
                print(f"Actual:   {current_data}")
                break
        
        if current_data:
            previous_data = current_data

        # Pausa breve para no saturar el puerto
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\nDetenido por el usuario.")
finally:
    ser.close()