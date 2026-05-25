import subprocess
import time
import sys

print("=== Checking Python3.14 environment ===")
python_path = r"C:/Users/nghil/AppData/Local/Programs/Python/Python314/python.exe"

if not __import__('os').path.exists(python_path):
    # Try to find Python using which/where
    import shutil
    python_path = shutil.which('python')
    print(f"Using: {python_path}")

print(f"\n=== Installing uvicorn ===")
result = subprocess.run([python_path, "-m", "pip", "install", "uvicorn", "--quiet"], capture_output=True, text=True)
if result.returncode == 0:
    print("✅ Uvicorn installed")
else:
    print(f"❌ Install failed: {result.stderr[:300]}")

print("\n=== Checking backend requirements ===")
result = subprocess.run([python_path, "-m", "pip", "install", 
    "sqlalchemy", "python-dotenv", "redis", "aiobotocore", "aiohttp", "httpx", "--quiet"], 
    capture_output=True, text=True)
if result.returncode == 0:
    print("✅ All dependencies installed")
else:
    print(f"Partial install. Output: {result.stderr[-200:]}")

print("\n=== Starting backend server ===")
result = subprocess.Popen(
    [python_path, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"],
    cwd=r"C:/Users/nghil/Projects/Hermes/suburb-intel/backend",
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
)

print("Server starting in background...")
time.sleep(5)

# Read server output
output = result.stdout.read()
if output:
    print(f"Server output:\n{output[-300:]}")

print("\n=== Testing API endpoints ===")

import urllib.request

def test_endpoint(url, name):
    try:
        response = urllib.request.urlopen(url, timeout=5)
        data = response.read().decode()[:500]  # First 500 chars
        print(f"✅ {name}: {response.status}")
        if "Swagger" in data or "OpenAPI" in data:
            print("   (API docs available)")
        elif len(data) < 20:
            print(f"   Response: {data.strip()}")
        else:
            print(f"   {data[:100]}...")
    except Exception as e:
        print(f"❌ {name}: {e}")

# Test various endpoints
endpoints = [
    ("http://localhost:8001/docs", "Health & API Docs"),
    ("http://localhost:8001/search/BALGARRY/property-rankings", "BALGARRY property rankings"),
    ("http://localhost:8001/search/KELLYS/property-rankings", "KELLYS property rankings"),
]

for url, name in endpoints:
    test_endpoint(url, name)

print("\n=== Testing Australian Gov Data APIs ===")
endpoints = [
    ("http://localhost:8001/search/BALGARRY/schools?gov_score=high", "High gov-score schools"),
    ("http://localhost:8001/search/BALGARRY/amenities?gov_score=low", "Low gov-score amenities"),
]

for url, name in endpoints:
    test_endpoint(url, name)

print("\n🎉 API tests complete!")
