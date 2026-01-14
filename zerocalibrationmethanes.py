import serial, time
ser = serial.Serial("COM8", 38400, bytesize=8, stopbits=2, parity='N', timeout=1)
def send(cmd):
    ser.write(cmd.encode('ascii')); time.sleep(2)
    print(cmd, "->", ser.read(100))
print("Go to configuration:"); send("[C]")   # expect b'[AK]'
print("Zero in fresh air:");  send("[E]")    # expect b'[AK]'
print("Back to normal:");     send("[A]")    # expect b'[AK]'
# optional settle
time.sleep(5)











