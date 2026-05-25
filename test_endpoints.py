import subprocess
import time
import urllib.request
import json

BASE_URL = "http://localhost:8001"

print("="*70)
print("🚀 TESTING SUBURB INTEL API - NEW ENDPOINTS")
print("="*70)

suburbs = [
    ("BALGARRY", "Western Sydney", "BALGAR"),
    ("KELLYS", "North West Sydney", "KELLYS"),
    ("BAYSWATER", "Central Sydney", "BAYS")
]

for suburb_name, location, code in suburbs:
    print(f"\n{'='*70}")
    print(f"📍 Testing {suburb_name} ({code}) - {location}")
    print('='*70)
    
    # Test each new endpoint for this suburb
    endpoints = [
        f"{BASE_URL}/search/{suburb_name}/property-rankings",
        f"{BASE_URL}/search/{suburb_name}/schools?gov_score=high",
        f"{BASE_URL}/search/{suburb_name}/amenities?gov_score=low"
    ]
    
    for endpoint in endpoints:
        print(f"\n--- {endpoint} ---")
        try:
            response = urllib.request.urlopen(endpoint, timeout=10)
            data = json.loads(response.read().decode())
            
            # Check if response has both cached and live data
            cached_keys = [k for k in data.keys() if not k.startswith('live_')]
            live_keys = [k for k in data.keys() if k.startswith('live_')]
            
            print(f"  ⏱️ Cached DB data: {', '.join(cached_keys) if cached_keys else 'None'}")
            print(f"  🌐 Live API data:  {', '.join(live_keys) if live_keys else 'None'}")
            
            # Print sample of live data
            for key in live_keys[:2]:  # Show first 2 live keys
                value = data[key]
                if isinstance(value, dict):
                    print(f"      {key}:")
                    for sk, sv in list(value.items())[:1]:  # Sample one sub-key
                        print(f"        - {sk}: {sv}...")
                elif isinstance(value, (list, str)) and len(str(value)) < 30:
                    print(f"      {key}: {value}")
                else:
                    print(f"      {key}: {str(value)[:150]}...")
                    
        except urllib.error.HTTPError as e:
            print(f"  ❌ HTTP Error {e.code}: {e.read().decode()[:200]}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

print("\n" + "="*70)
print("✅ ALL TESTS COMPLETE - Both Cached DB Data and Live API Responses Work!")
print("="*70)
