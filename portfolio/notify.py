"""Notification stub. Discord webhook wiring comes later — routines call
send() now so nothing changes when DISCORD_WEBHOOK_URL gets set."""

import json
import os
import urllib.request


def send(text: str) -> None:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        print(f"[notify skipped — DISCORD_WEBHOOK_URL not set]\n{text}")
        return
    req = urllib.request.Request(
        url,
        data=json.dumps({"content": text[:1900]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)
