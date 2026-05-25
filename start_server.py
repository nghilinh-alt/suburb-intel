import subprocess
import time
import sys

# Start backend in background
python314 = r"C:/Users/nghil/AppData/Local/Programs/Python/Python314/python.exe"
backend_dir = r"C:/Users/nghil/Projects/Hermes/suburb-intel/backend"

print("🔧 Starting backend server...")
proc = subprocess.Popen(
    [python314, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"],
    cwd=backend_dir,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
)

print("Waiting 5 seconds for server to start...")
time.sleep(5)

# Read any startup output
output = proc.stdout.read()
if output:
    print(output.decode())

import urllib.request

# Test health endpoint first
try:
    response = urllib.request.urlopen(f"{python314}", timeout=5)
except:
    pass

# Try to connect
test_url = "http://localhost:8001/health"
print("\n🔍 Checking server health...")
try:
    r = urllib.request.urlopen(test_url, timeout=10)
    print(f"✅ Server is running! Health: {r.read().decode()}")
except Exception as e:
    print(f"❌ Server not responding: {e}")
    print("\nTrying to start server in foreground...")
    
    # Start server for user to see output
    proc.start()
