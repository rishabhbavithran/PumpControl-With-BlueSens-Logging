from pymodbus.client import ModbusSerialClient as ModbusClient
import struct
import time
import csv
import serial
import pandas as pd
import matplotlib.pyplot as plt
import re
import os 
with open("bluesens.pid", "w") as f:
    f.write(str(os.getpid()))

# === Utility Functions ===

def decode_modbus_swapped_float(registers):
    if len(registers) != 2:
        raise ValueError("Expected 2 registers for a float")
    high_word = registers[0]
    low_word = registers[1]
    packed_bytes = struct.pack('>HH', low_word, high_word)
    return struct.unpack('>f', packed_bytes)[0]

def decode_ascii_string(registers):
    byte_chunks = []
    for reg in registers:
        packed = struct.pack('>H', reg)
        reversed_bytes = packed[::-1]
        byte_chunks.append(reversed_bytes)
    swapped_bytes = b''.join(byte_chunks)
    return swapped_bytes.decode('ascii').strip()

def read_gas_type(client, address):
    result = client.read_holding_registers(address=address, count=3)
    if result.isError():
        return "Unknown"
    return decode_ascii_string(result.registers)

def read_live_value(client, address, label):
    result = client.read_holding_registers(address=address, count=2)
    if result.isError():
        print(f" Error reading {label} at {address}")
        return None
    value = decode_modbus_swapped_float(result.registers)
    print(f"{label}: {value}")
    return value

def read_live_value_oxygen():
    ser.write(b'&e\r')
    response = ser.readline()
    decoded = response.decode().strip()
    parts = decoded.split()

    if len(parts) >= 3:
        try:
            oxygen = float(parts[0])
            pressure = float(parts[1])
            print(f"O₂ Concentration: {oxygen}")
            print(f"O₂ Pressure: {pressure}")
            return oxygen, pressure
        except ValueError:
            print("Could not convert O2/Pressure to float")
            return None, None
    else:
        print("Unexpected O2 response format")
        return None, None

# === Modbus Setup ===

def safe_connect_modbus(port, baudrate=38400, timeout=1, retries=3, delay=2):
    for attempt in range(retries):
        client = ModbusClient(port=port, baudrate=baudrate, timeout=timeout)
        if client.connect():
            print(f"✅ Connected to Modbus on {port}")
            return client
        else:
            print(f"⚠️ Modbus connect failed on {port}, retrying... ({attempt+1}/{retries})")
            time.sleep(delay)
    raise Exception(f"❌ Could not connect to Modbus on {port} after {retries} attempts.")

def safe_open_serial(port, baudrate=19200, timeout=2, retries=3, delay=2):
    for attempt in range(retries):
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout
            )
            if ser.is_open:
                print(f"✅ Opened serial port {port}")
                return ser
        except serial.SerialException as e:
            print(f"⚠️ Serial open failed on {port}, retrying... ({attempt+1}/{retries})")
            time.sleep(delay)
    raise Exception(f"❌ Could not open serial port {port} after {retries} attempts.")


try:
    client = safe_connect_modbus(port='COM6')
    ser = safe_open_serial(port='COM7')
except Exception as e:
    print(e)
    exit(1)

LOG_INTERVAL = 1800  # seconds between CSV writes
last_log_time = time.time()

if client.connect() and ser.is_open:
    print(" Connected to COM5 and COM4")

    try:
        result = client.read_holding_registers(address=118, count=1, slave=1)
        if not result.isError():
            print(f"Sensor Modbus Address (from register 118): {result.registers[0]}")
        else:
            print("Could not read register 118")

        gas1 = read_gas_type(client, 4240)
        gas2 = read_gas_type(client, 4336)
        gas1 = re.sub(r'[^\x20-\x7E]', '', gas1).strip()
        gas2 = re.sub(r'[^\x20-\x7E]', '', gas2).strip()

        print(f"Channel 1 gas type: {gas1}")
        print(f"Channel 2 gas type: {gas2}")
        print("\n📡 Starting live readings...\n")

        # === CSV Setup ===
 # === Generate a timestamped filename ===

        output_dir = r'C:\Users\bk\OneDrive\Desktop\GasConcentrations'
        os.makedirs(output_dir, exist_ok=True)  # Create the directory if it doesn't exist

        start_time_str = time.strftime('%Y-%m-%d_%H-%M-%S')
        filename = os.path.join(output_dir, f'gas_log_{start_time_str}.csv')
        csv_file = open(filename, mode='w', newline='', encoding='utf-8')
        csv_writer = csv.writer(csv_file)

        # === Write CSV header ===
        csv_writer.writerow([
            'Timestamp',
            f'{gas1}',
            f'{gas2}',
            'O2 Concentration',
            'Pressure',
            'Relative Humidity',
            'Absolute Humidity',
            'Gas Temperature',
            'O2Pressure'
        ])

        csv_writer = csv.writer(csv_file)
        if csv_file.tell() == 0:
            csv_writer.writerow([
                'Timestamp',
                f'{gas1}',
                f'{gas2}',
                'O2 Concentration',
                'Pressure',
                'Relative Humidity',
                'Absolute Humidity',
                'Gas Temperature',
                'O2Pressure'
            ])

        while True:
            # Collect all readings
            val1 = read_live_value(client, 4096, f"{gas1} (Live, Channel 1)")
            val2 = read_live_value(client, 4128, f"{gas2} (Live, Channel 2)")
            pressure = read_live_value(client, 4192, "Pressure")
            rh = read_live_value(client, 4194, "Relative Humidity")
            ah = read_live_value(client, 4196, "Absolute Humidity")
            temp = read_live_value(client, 4198, "Gas Temperature")
            o2_conc, o2_pressure = read_live_value_oxygen()

            # Write to CSV every 30 seconds
            now = time.time()
            if now - last_log_time >= LOG_INTERVAL:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                csv_writer.writerow([
                    timestamp, val1, val2, o2_conc,pressure, rh, ah, temp, o2_pressure
                ])
                csv_file.flush()
                print(f"📁 Data logged at {timestamp}")
                last_log_time = now

            print("-" * 50)
            time.sleep(2)

    except KeyboardInterrupt:
        print("Stopped by user")

    except Exception as e:
        print("Exception occurred:", e)

    finally:
        csv_file.close()
        client.close()
        print("Disconnected from sensor and closed CSV file")

        try:
            time.sleep(2)
            df = pd.read_csv(filename)
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])

            plt.figure(figsize=(10, 6))
            plt.plot(df["Timestamp"], df[gas1], label=gas1)
            plt.plot(df["Timestamp"], df[gas2], label=gas2)
            plt.plot(df["Timestamp"], df["O2 Concentration"], label="O2 Concentration")

            plt.xlabel("Time")
            plt.ylabel("Gas Concentration")
            plt.title("Gas Concentrations Over Time")
            plt.legend()
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f"{filename.replace('.csv', '')}_plot.png", dpi=300)
            plt.show()
            print("Plot saved and displayed.")
        except Exception as e:
            print("Plotting failed:", e)

else:
    print("Failed to connect to COM5 or COM4")