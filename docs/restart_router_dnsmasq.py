#!/usr/bin/env python3
"""Restart dnsmasq on OpenWrt router at 192.168.1.1 via ubus RPC."""
import urllib.request
import json

ROUTER_IP = "192.168.1.1"
PASSWORD = "Tr33f3ll@1978!Openwrt"


def ubus(token, obj, method, params=None):
    url = f"http://{ROUTER_IP}/ubus"
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "call",
        "params": [token, obj, method, params or {}]
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


login_payload = {
    "jsonrpc": "2.0", "id": 1, "method": "call",
    "params": ["00000000000000000000000000000000", "session", "login",
               {"username": "root", "password": PASSWORD}]
}
data = json.dumps(login_payload).encode()
req = urllib.request.Request(f"http://{ROUTER_IP}/ubus", data=data,
                              headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=10) as resp:
    result = json.loads(resp.read())
token = result["result"][1]["ubus_rpc_session"]
print(f"Logged in. Token: {token[:8]}...")

result = ubus(token, "luci", "setInitAction", {"name": "dnsmasq", "action": "restart"})
print(f"Restart result: {result}")
