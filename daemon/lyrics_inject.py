#!/usr/bin/env python3
"""Send a demo song's synced lyrics to the Clawdmeter over BLE (Phase 2 test).

Reuses the daemon's macOS approach: the board is auto-connected by the OS as an
HID keyboard, so we grab that system-connected peripheral rather than scanning.
Then streams: lh header -> ll lines -> lp position, to the RX characteristic.
"""
import asyncio
import json
import sys
import time

from bleak import BleakClient, BleakScanner

SERVICE_UUID = "4c41555a-4465-7669-6365-000000000001"
RX_CHAR_UUID = "4c41555a-4465-7669-6365-000000000002"
DEVICE_NAME  = "Clawdmeter"

TRACK_ID = 3735928559  # 0xDEADBEEF-ish; any stable int
SONG = ("This Love", "Maroon 5", [
    (20330, "I was so high, I did not recognize"),
    (23980, "The fire burning in her eyes"),
    (26560, "The chaos that controlled my mind"),
    (30520, "Whispered goodbye as she got on a plane"),
    (34170, "Never to return again but always in my heart, oh"),
    (41020, "This love has taken its toll on me"),
    (45360, "She said goodbye too many times before"),
    (50900, "And her heart is breakin' in front of me"),
    (55470, "And I have no choice"),
    (57730, "'Cause I won't say goodbye anymore"),
    (71190, "I tried my best to feed her appetite"),
    (74530, "Keep her coming every night"),
    (76930, "So hard to keep her satisfied, oh"),
    (80870, "Kept playing love like it was just a game"),
    (84320, "Pretending to feel the same"),
    (86930, "Then turn around and leave again, but uh-oh"),
    (91539, "This love has taken its toll on me"),
    (95830, "She said goodbye too many times before"),
])


def log(m): print(m, flush=True)


async def retrieve_connected_macos():
    """Grab the system-connected Clawdmeter via CoreBluetooth (like the daemon)."""
    from bleak.backends.corebluetooth.CentralManagerDelegate import CentralManagerDelegate
    from bleak.backends.device import BLEDevice
    from CoreBluetooth import CBUUID

    mgr = CentralManagerDelegate()
    await mgr.wait_until_ready()
    cm = mgr.central_manager

    for uuid, need_name in ((SERVICE_UUID, False), ("1812", True)):
        peris = cm.retrieveConnectedPeripheralsWithServices_([CBUUID.UUIDWithString_(uuid)])
        for p in peris or []:
            if need_name and p.name() != DEVICE_NAME:
                continue
            addr = p.identifier().UUIDString()
            log(f"system-connected peripheral: {p.name()!r} [{addr}]")
            return BLEDevice(addr, p.name(), (p, mgr), rssi=-60)
    return None


async def find_target():
    if sys.platform == "darwin":
        dev = await retrieve_connected_macos()
        if dev:
            return dev
        log("not held by OS; falling back to a name scan…")
    return await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=10.0)


async def send(client, obj):
    data = json.dumps(obj, separators=(",", ":")).encode()
    await client.write_gatt_char(RX_CHAR_UUID, data, response=False)


async def main():
    dev = await find_target()
    if not dev:
        log("Clawdmeter not found. Is it paired/connected to this Mac?")
        return 1
    log(f"connecting to {dev}…")
    async with BleakClient(dev) as client:
        log("connected. streaming lyrics…")
        track, artist, lines = SONG
        await send(client, {"ly": "h", "id": TRACK_ID, "n": len(lines),
                            "tr": track, "ar": artist})
        for i, (ms, text) in enumerate(lines):
            await send(client, {"ly": "l", "id": TRACK_ID, "i": i, "ms": ms, "x": text})
            await asyncio.sleep(0.012)   # gentle pacing; ring buffer covers bursts
        # start playback mid-verse so scrolling is immediately visible
        await send(client, {"ly": "p", "id": TRACK_ID, "ms": 30000, "pl": 1})
        log(f"sent header + {len(lines)} lines + position. holding link 3s…")
        await asyncio.sleep(3.0)
    log("done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
