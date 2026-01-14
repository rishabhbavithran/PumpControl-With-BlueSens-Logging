import serial
import time
import sys
import os
import subprocess
import signal

ser = serial.Serial('COM10', baudrate=19200, timeout=1)
time.sleep(2)

def send_command(cmd):
    full_cmd = cmd.strip().upper() + '\r'
    ser.write(full_cmd.encode())
    time.sleep(0.2)
    response = ser.read_all().decode(errors='ignore')
    print(f">> {cmd}")
    print("<<", response)

def run_for_duration(command, duration):
    send_command(command)
    time.sleep(0.2)
    send_command('RUN')
    start = time.time()
    try:
        while time.time() - start < duration:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nInterrupted during command execution.")
        send_command('STP')
        raise
    send_command('STP')
    time.sleep(0.2)

def setup_pump():
    send_command('STP')
    time.sleep(0.5)
    send_command('DIA 3/16')
    time.sleep(0.5)
    send_command('RAT 250.0 MM')
    time.sleep(0.5)
    send_command('VOL 0')
    time.sleep(0.5)

def bacteria_dispersion():
    bacteria_dispersion_duration = 90
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
    removal_duration = 200
    print(f"Emptying Notebook for {removal_duration} seconds...")

    run_for_duration('DIR WDR', removal_duration)
    send_command('STP')
    time.sleep(0.2)

def regeneration():
    regeneration_time = 3600
    print("MAKE SURE VALVE 3 IS CLOSED")
    print(f"Regenration Cycle for {regeneration_time} seconds...")

    run_for_duration('DIR INF', regeneration_time)
    send_command('STP')
    time.sleep(0.2)

def methanol_production(lt, gt, ot):
    print("Starting Methanol Production Cycle...")
    script_path = r"C:\Users\bk\Scripts\bluesens.py"
    # Launch run_bluesens.py in a new terminal window
    bluesens_process = subprocess.Popen(
        [sys.executable, script_path],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )

    send_command('DIR INF')
    time.sleep(0.2)
    send_command('RUN')

    elapsed_time = time.time()
    start_time = time.time()
    liquid_cycle = True
    gas_cycle = False

    try:
        while time.time() - start_time <= ot:
            if time.time() - elapsed_time > lt and liquid_cycle:
                elapsed_time = time.time()
                print("Gas cycle running")
                send_command('DIR WDR')
                liquid_cycle = False
                gas_cycle = True
                remaining_time = int((ot - (time.time() - start_time))/60)
                print(f"Remaining Time : {remaining_time} minutes")

            elif time.time() - elapsed_time > gt and gas_cycle:
                elapsed_time = time.time()
                print("Liquid cycle running")
                send_command('DIR INF')
                liquid_cycle = True
                gas_cycle = False
                remaining_time = int((ot - (time.time() - start_time))/60)
                print(f"Remaining Time : {remaining_time} minutes")

            time.sleep(0.1)

        send_command('STP')
        time.sleep(0.2)
        print("Methanol Production completed.")
        fluid_removal()

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected during methanol production.")
        send_command('STP')
        raise

    finally:
        try:
            with open("bluesens.pid", "r") as f:
                fluid_removal()

                bluesens_process.send_signal(signal.CTRL_BREAK_EVENT)
                bluesens_process.wait()  # Wait for it to finish plotting
                print("run_bluesens.py terminated.")
        except Exception as e:
            print(f"Could not terminate run_bluesens.py: {e}")

def get_process_choice():
    print("""
Scheduling Process

Please Enter the process:

1. Press r for fluid removal (CLOSE VALVE 4)
2. Press m for methanol production after filling system with gases (CLOSE VALVES 3 AND 4)
3. Press g for regeneration after filling system with gases (CLOSE VALVE 3 AND 4) 
""")
    return input("Enter your choice: ").strip().lower()

def emergency_stop():
    print("\nEmergency Stop: Stopping pump and closing serial port...")
    send_command('STP')
    send_command('DIR WDR')
    time.sleep(2)
    send_command('STP')

    # Kill bluesens if running
    try:
        with open("bluesens.pid", "r") as f:
            bluesens_pid = int(f.read())
            os.kill(bluesens_pid, signal.SIGTERM)
            print("run_bluesens.py terminated due to emergency stop.")
    except Exception:
        pass

    ser.close()
    print("Serial port closed.")
    sys.exit(0)

def main():
    try:
        setup_pump()
        # lt = int(input("Enter liquid cycle time (in seconds): "))
        # gt = int(input("Enter gas cycle time (in seconds): "))
        # ot = int(input("Enter overall time (in minutes): ")) * 60

        lt = 160
        gt = 160
        ot = 7200

        while True:
            choice = get_process_choice()

            if choice == 'm':
                #bacteria_dispersion()
                #fluid_removal()
                print("PLEASE CHECK IF CLAMPS ARE OPEN")
                time.sleep(1)
                setup_pump()
                methanol_production(lt, gt, ot)
                #print("Automatic process completed.\n")

            elif choice == 'r':
                fluid_removal()

            elif choice == 'g':
                regeneration()

            else:
                print("Invalid input. Please try again.\n")

    except KeyboardInterrupt:
        emergency_stop()

if __name__ == "__main__":
    main()
