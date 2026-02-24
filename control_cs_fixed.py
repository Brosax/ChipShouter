import time
import sys

try:
    from chipshouter import ChipSHOUTER
except ImportError:
    print("Error: chipshouter library not found. Please install it using 'pip install chipshouter'")
    sys.exit(1)

def run_pulse_sequence(port='COM7'):
    print(f"Connecting to ChipSHOUTER on {port}...")
    try:
        cs = ChipSHOUTER(port)
        print("Connected.")
    except Exception as e:
        print(f"Failed to connect to ChipSHOUTER on {port}: {e}")
        return

    try:
        # Configuration
        target_voltage = 300
        print(f"Setting voltage to {target_voltage}V...")
        cs.voltage = target_voltage
        
        # Mute
        print("Muting device (disable sound)...")
        cs.mute = True
        
        # Arm
        if cs.armed:
            print("Device is already armed.")
        else:
            print("Arming device...")
            cs.armed = True
        
        # Wait a moment for charge/stabilization
        time.sleep(1) 
        
        # Pulse
        print("Sending single pulse...")
        # cs.pulse is a property returning PulseSettings, but the setter triggers a pulse.
        # cs.pulse = True triggers a pulse.
        cs.pulse = True
        
        print("Pulse sent successfully.")
        
        # Disarm
        print("Disarming device...")
        cs.armed = False
        print("Device disarmed.")

    except Exception as e:
        print(f"An error occurred during operation: {e}")
        import traceback
        traceback.print_exc()
    finally:
         # Close connection if possible
        try:
             # Some versions might support close, others rely on destruction
            if hasattr(cs, 'close'):
                cs.close()
            else:
                del cs
            print("Connection closed/cleaned up.")
        except:
            pass

if __name__ == "__main__":
    run_pulse_sequence()
