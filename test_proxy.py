# -*- coding: utf-8 -*-
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Free proxy list (frequently updated)
proxies_list = [
    "http://43.134.68.153:3128",  # Hong Kong
    "http://8.213.128.6:80",       # Singapore
    "http://47.88.62.42:80",       # Japan
    "http://185.162.231.106:80",   # Europe
    "http://47.74.152.29:8888",    # Asia
]

print("Testing free proxies...\n")

for proxy_url in proxies_list:
    try:
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }

        print(f"Testing: {proxy_url}")
        response = requests.get('https://api.binance.com/api/v3/ping',
                               proxies=proxies,
                               timeout=5,
                               verify=False)

        if response.status_code == 200:
            print(f"\n[SUCCESS] Use this proxy:")
            print(f"proxy_config = {{'http': '{proxy_url}', 'https': '{proxy_url}'}}")
            print()
            break
    except Exception as e:
        print(f"[FAILED] {str(e)[:60]}")
        continue
else:
    print("\n[WARNING] All proxies failed. Try:")
    print("1. ProtonVPN (free)")
    print("2. Tor Browser + SOCKS5")
    print("3. Mobile hotspot")
