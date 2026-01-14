import serial, time, re

def calibrationfn(ch4_notcorrected):
    corrected = 0.9409*ch4_notcorrected - 0.0201
    return corrected


PORT = "COM8"
BAUD = 38400
ser = serial.Serial(PORT, BAUD, bytesize=8, stopbits=2, parity='N', timeout=1)
time.sleep(2)
print("Reading methane (Normal Mode)...\n")
collecting = False
fields = []
def is_hex8(s):
    return bool(re.fullmatch(r'[0-9A-Fa-f]{8}', s))
while True:
    line = ser.readline().decode(errors="ignore").strip().lower()
    if not line:
        continue
    # Start of frame
    if line in ('[', '0000005b'):
        collecting = True
        fields = []
        continue
    # End of frame
    if line in (']', '0000005d'):
        if collecting and len(fields) >= 3:
            try:
                ch4_hex = fields[0]
                temp_hex = fields[2]
                ch4_ppm = int(ch4_hex, 16)
                ch4_percent = ch4_ppm / 10000.0  # 10,000 ppm = 1 %vol
                ch4_corrected = calibrationfn(ch4_percent)
                temp_raw = int(temp_hex, 16)
                #print("Temp Raw ", temp_raw)
                #print("CH4 Ppm raw", ch4_ppm)
                temp_k = temp_raw / 10.0          # convert to Kelvin
                temp_c = temp_k - 273.15          # convert to Celsius
                print(f"CH4 : {ch4_corrected:.4f} %vol")
                print("--------------------------------------------------------------------------")
                time.sleep(1)
            except ValueError:
                print("Frame parse error:", fields)
        collecting = False
        fields = []
        continue
    # print("Fields : ")
    # print(fields)
    # Add valid 8-hex lines to buffer
    if collecting and is_hex8(line):
        fields.append(line)









