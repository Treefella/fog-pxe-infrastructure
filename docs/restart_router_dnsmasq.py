#!/usr/bin/env python3
"""
Restart dnsmasq on an OpenWrt router via ubus RPC.

Usage:
    ROUTER_IP=10.0.0.1 ROUTER_PASSWORD=yourpassword python3 restart_router_dnsmasq.py

Never hardcode credentials — pass them via environment variables.
"""
import json
import os
import sys
import urllib.request

ROUTER_IP = os.environ.get("ROUTER_IP", "10.0.0.1")
PASSWORD = os.environ.get("ROUTER_PASSWORD")

if not PASSWORD:
    sys.exit("ERROR: ROUTER_PASSWORD environment variable is not set.")


def ubus(token, obj, method, params=None):
    url = f"http://{ROUTER_IP}/ubus"
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "call",
        "params": [token, obj, method, params or {}],
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


login_payload = {
    "jsonrpc": "2.0", "id": 1, "method": "call",
    "params": [
        "00000000000000000000000000000000", "session", "login",
        {"username": "root", "password": PASSWORD},
    ],
}
data = json.dumps(login_payload).encode()
req = urllib.request.Request(
    f"http://{ROUTER_IP}/ubus", data=data,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=10) as resp:
    result = json.loads(resp.read())

token = result["result"][1]["ubus_rpc_session"]
print(f"Logged in. Token: {token[:8]}...")

result = ubus(token, "luci", "setInitAction", {"name": "dnsmasq", "action": "restart"})
print(f"Restart result: {result}")
