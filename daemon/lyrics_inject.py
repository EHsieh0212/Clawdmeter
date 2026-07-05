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
# A visibly different song from the serial demo (This Love), so a successful
# render unambiguously proves the lyrics arrived over BLE.
SONG = ("Bohemian Rhapsody", "Queen", [
    (670,   "Is this the real life? Is this just fantasy?"),
    (7710,  "Caught in a landslide, no escape from reality"),
    (15150, "Open your eyes, look up to the skies and see"),
    (25680, "I'm just a poor boy, I need no sympathy"),
    (31530, "Because I'm easy come, easy go, little high, little low"),
    (38590, "Any way the wind blows doesn't really matter to me, to me"),
    (55950, "Mama, just killed a man"),
    (62460, "Put a gun against his head, pulled my trigger, now he's dead"),
    (71000, "Mama, life had just begun"),
    (77000, "But now I've gone and thrown it all away"),
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
