"""
Test rapide de l'API KB
"""

import requests

# Test 1: Get stats
print("=" * 60)
print("TEST 1: GET /api/kb/stats")
print("=" * 60)
response = requests.get("http://localhost:8000/api/kb/stats")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

print("\n" + "=" * 60)
print("TEST TERMINE")
print("=" * 60)
