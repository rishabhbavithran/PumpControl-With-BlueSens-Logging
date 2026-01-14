import serial
import time
import sys
import csv
import threading
import minimalmodbus
# ------------ MODBUS SETTINGS ------------
MODBUS_PORT = 'COM11'
SLAVE_ID = 1
CHANNEL_REGISTER = 48
FUNCTION_CODE = 4
FULL_SCALE = 5.0
SAVE_PATH = r"C:\Users\bk\OneDrive\Desktop\PressureLog"
#FILENAME = "pressure_log.csv"
# ------------ PUMP SETTINGS ------------
PUMP_PORT = 'COM9'
ser = serial.Serial(PUMP_PORT, baudrate=19200, timeout=1)
# ------------ THREADING CONTROL ------------
# This event acts as a "Start/Stop" signal for the background thread
log_trigger = threading.Event()
stop_everything = threading.Event()
# ------------------------------------------
# MODBUS LOGIC
# ------------------------------------------
def counts_to_volts_pmFS(raw: int, fs: float) -> float:
    return (raw / 65535.0) * (2.0 * fs) - fs
def pressure_logger_worker():
    """Background task that waits for the signal to record data."""
    instrument = minimalmodbus.Instrument(MODBUS_PORT, SLAVE_ID)
    instrument.serial.baudrate = 9600
    instrument.serial.timeout = 1.0
    while not stop_everything.is_set():
        # If the trigger is set, start logging
        if log_trigger.is_set():
            timestamp_str = time.strftime('%Y%m%d_%H%M%S')
            current_filename = f"pressure_log_{timestamp_str}.csv"
            with open(f"{SAVE_PATH}\\{current_filename}", mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Pressure (psi a)"])
                print("\n[LOGGER] Pressure logging started.")
                while log_trigger.is_set() and not stop_everything.is_set():
                    try:
                        raw = instrument.read_register(CHANNEL_REGISTER, functioncode=FUNCTION_CODE)
                        volts = counts_to_volts_pmFS(raw, FULL_SCALE)
                        pressure = (volts - 1) / (5 - 1) * 50
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        writer.writerow([timestamp, f"{pressure:.2f}"])
                        file.flush()
                        print(f"[{timestamp}] P={pressure: .2f} psi a (Saved)")
                    except Exception as e:
                        print(f"\n[LOGGER ERROR]: {e}")
                    time.sleep(10.0) # Frequency of logging
                print("\n[LOGGER] Pressure logging stopped.")
        else:
            # If trigger is off, just wait a bit and check again
            time.sleep(0.5)
# ------------------------------------------
# PUMP CONTROL LOGIC
# ------------------------------------------
def send_command(cmd):
    full_cmd = cmd.strip().upper() + '\r'
    ser.write(full_cmd.encode())
    time.sleep(0.2)
    response = ser.read_all().decode(errors='ignore')
    print(f">> {cmd} | << {response.strip()}")
def run_for_duration(command, duration):
    send_command(command)
    time.sleep(0.2)
    send_command('RUN')
    start = time.time()
    try:
        while time.time() - start < duration:
            time.sleep(0.1)
    except KeyboardInterrupt:
        send_command('STP')
        raise
    send_command('STP')
def setup_pump():
    send_command('STP')
    time.sleep(0.1)
    send_command('DIA 3/16')
    time.sleep(0.1)
    send_command('RAT 350.0 MM')
    time.sleep(0.1)
    send_command('VOL 0')
    time.sleep(0.1)

def bacteria_dispersion():
    bacteria_dispersion_duration = 120
    print(f"Bacteria Delivery for {bacteria_dispersion_duration} seconds...")

    run_for_duration('DIR INF', bacteria_dispersion_duration)
    send_command('STP')
    time.sleep(0.2)

def sterlization():
    print("Please change bottle of experiment to bottle containing sterlization liquid ")
    st = int(input("Enter sterlization cycle time (in seconds): "))    
    print(f"Sterlization for {st} seconds...")

    run_for_duration('DIR INF', st)
    send_command('STP')
    time.sleep(0.2)
    
def fluid_removal():
    removal_duration = 120
    print(f"Emptying Notebook for {removal_duration} seconds...")

    run_for_duration('DIR WDR', removal_duration)
    send_command('STP')
    time.sleep(0.2)

def methanol_production(lt, gt, ot):
    print("\n--- Starting Methanol Production Cycle ---")
    # 1. TURN ON THE LOGGER
    log_trigger.set()
    send_command('DIR INF')
    send_command('RUN')
    elapsed_time = time.time()
    start_time = time.time()
    liquid_cycle = True
    gas_cycle = False
    try:
        while time.time() - start_time <= ot:
            if time.time() - elapsed_time > lt and liquid_cycle:
                elapsed_time = time.time()
                print("Switching to Gas cycle...")
                send_command('STP')
                time.sleep(0.1)
                send_command('DIR WDR')
                time.sleep(0.1)
                send_command('RUN')
                time.sleep(0.1)
                liquid_cycle, gas_cycle = False, True
            elif time.time() - elapsed_time > gt and gas_cycle:
                elapsed_time = time.time()
                print("Switching to Liquid cycle...")
                send_command('STP')
                time.sleep(0.1)
                send_command('DIR INF')
                time.sleep(0.1)
                send_command('RUN')
                time.sleep(0.1)
                liquid_cycle, gas_cycle = True, False
            time.sleep(0.1)
        send_command('STP')
        print("Methanol Production completed.")
    finally:
        # 2. TURN OFF THE LOGGER (even if there is an error)
        log_trigger.clear()


def main():
    # Start the background thread immediately
    logger_thread = threading.Thread(target=pressure_logger_worker, daemon=True)
    logger_thread.start()
    try:
        setup_pump()
        # Get inputs once or move inside the loop as needed
        lt = int(input("Enter liquid cycle time (s): "))
        gt = int(input("Enter gas cycle time (s): "))
        ot = int(input("Enter overall time (min): ")) * 60
        while True:
            print("\n1. Auto (Bact. del + Removal + Methanol): Press 1 or a\n2. Bacteria\n3. Removal\n4. Methanol\n5. Sterilization")
            choice = input("Choice: ").lower()
            if choice == 'm' or choice == '4':
                methanol_production(lt, gt, ot)
            elif choice == 'a' or choice == '1':
                bacteria_dispersion()
                fluid_removal()
                methanol_production(lt, gt, ot)
            elif choice == 'b' or choice == '3':
                bacteria_dispersion()

            elif choice == 'r' or choice == '3':
                fluid_removal()

            elif choice == 's' or choice == '5':
                sterlization()

            # ... (Add other choices here)
    except KeyboardInterrupt:
        print("\nEmergency Stop Triggered.")
        log_trigger.clear()
        stop_everything.set()
        send_command('STP')
        time.sleep(0.1)
        ser.close()
if __name__ == "__main__":
    main()

