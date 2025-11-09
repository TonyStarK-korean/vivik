import requests
import sys

print("=== Binance IP Ban Test ===")
print("Testing Binance API access...")

try:
    response = requests.get("https://fapi.binance.com/fapi/v1/ping", timeout=10)
    
    if response.status_code == 200:
        print("SUCCESS: No IP ban - Trading ready!")
        print("Status: CLEAR")
    elif response.status_code == 418:
        print("ERROR: IP ban confirmed (418)")
        retry_after = response.headers.get('retry-after', 'unknown')
        print(f"Retry-After: {retry_after} seconds")
        print("Status: BANNED")
        print("Solution: Use VPN or wait")
    elif response.status_code == 429:
        print("WARNING: Rate limit (429)")
        print("Status: RATE_LIMITED")
    else:
        print(f"UNKNOWN: Status code {response.status_code}")
        print("Status: UNKNOWN")
        
except Exception as e:
    print(f"NETWORK ERROR: {e}")
    print("Status: CONNECTION_FAILED")
    print("Possible causes: No internet, VPN issues, or severe ban")

# Current IP check
try:
    print("\nChecking current IP...")
    ip_response = requests.get("https://api.ipify.org", timeout=5)
    print(f"Current IP: {ip_response.text}")
except:
    print("Could not get IP address")