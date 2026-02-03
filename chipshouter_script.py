import time
from chipshouter import ChipSHOUTER
from chipshouter.com_tools import Reset_Exception

# 1. Inicializar la conexión
# Sustituya "COM" por el número de puerto real que aparece en su administrador de dispositivos
cs = ChipSHOUTER("COM7") 


# 2. Configurar parámetros 
#       _________________________________________ repeat (3)
#      |                  |                  |
#      v                  v                  v
#    ____               ____               ____
# __|    |_____________|    |_____________|    |____________
#     ^       ^
#     |        \__ Dead time
#     |___ pulse width 

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


while True:
    try:
        count = 0
        while True:
            cs.pulse = 1        # Enviar un pulso de inyección 
            count += 1

            #print(f'statu = >',cs.state ) 
            print("recuentos -> ", count)

            # Realizar una autocomprobación de seguridad
            # if count % 100 == 0:
            #     if not cs.trigger_safe:
            #         time.sleep(1.5)

            time.sleep(intervalo)    # Intervalo de retardo 
            
    except Reset_Exception:
        print("Device rebooted!")
        time.sleep(5) #Need to wait after reboot!
        setup_device()
    except KeyboardInterrupt:
        print("\nDetenido por el usuario...")
        break 
    finally:
        cs.armed = 0         
