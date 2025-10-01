import asyncio
import json
import time
import locale
from bleak import BleakScanner, BleakClient

def handle_prompt_fields(cmd_meta):
    data = {}
    for field in cmd_meta.get("prompt", []):
        val = input(f"{field}: ")
        data[field.lower()] = val
    return data

def build_command(cmd_code, device_id, data=None):
    payload = {
        "c": cmd_code,
        "d": {"device_id": device_id}
    }
    if data:
        payload["d"].update(data)
    return json.dumps(payload).encode()

def notification_handler(sender, data):
    print(f"[Notification] From {sender}: {data.decode(errors='ignore')}")

async def scan_for_ble():
    print("Scanning for nearby BLE devices (5s)...")
    devices = await BleakScanner.discover(timeout=5.0)

    if not devices:
        print("[-] No devices found.")
        return None

    # Display numbered list
    for i, device in enumerate(devices):
        name = device.name or "Unknown"
        print(f"[{i}] {name} ({device.address})")

    while True:
        try:
            choice = input("Select device to connect (number): ").strip()
            if choice.isdigit():
                index = int(choice)
                if 0 <= index < len(devices):
                    return devices[index].address
            print("Invalid selection. Try again.")
        except KeyboardInterrupt:
            print("\n[-] Aborted.")
            return None


def print_available_characteristics(client):
    print("\n[+] Available GATT Services and Characteristics:")
    for service in client.services:
        print(f"  [Service] {service.uuid}")
        for char in service.characteristics:
            props = ', '.join(char.properties)
            print(f"    └── [Char] {char.uuid} ({props})")
    print()

async def interact_with_device(address):
    async with BleakClient(address) as client:
        print("[*] Connected to", address)

        #await client.start_notify(NOTIFY_CHAR_UUID, notification_handler)

        # Print all available characteristics right after connection
        print_available_characteristics(client)

        print("Successfully connected. What would you like to send? (type 'help' for options)")

        while True:
            try:
                user_input = input("> ").strip().lower()
                if not user_input:
                    continue
                if user_input in ("exit", "quit"):
                    break
                if user_input == "help":
                    print_help()
                    continue

                cmd_meta = COMMANDS.get(user_input)
                if not cmd_meta:
                    if user_input.startswith("{"):
                        payload = user_input.encode()
                        await client.write_gatt_char(WRITE_CHAR_UUID, payload)
                        print("[*] Raw JSON command sent.")
                    else:
                        print("[!] Unknown command. Type 'help' to list available commands.")
                    continue

                if cmd_meta.get("type") == "read":
                    value = await client.read_gatt_char(cmd_meta["uuid"])
                    print(f"[<] Read from {cmd_meta['uuid']}: {value.decode(errors='ignore')}")
                    continue

                if "prompt" in cmd_meta:
                    data = handle_prompt_fields(cmd_meta)
                    payload = build_command(user_input, DEVICE_ID, data)
                elif "payload_func" in cmd_meta:
                    payload = cmd_meta["payload_func"]()
                else:
                    payload = cmd_meta["payload"]

                await client.write_gatt_char(cmd_meta["uuid"], payload)
                print("[*] Command sent.")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("Error:", e)

        print("Disconnected.")

async def main():
    address = await scan_for_ble()
    if not address:
        return
    await interact_with_device(address)


if __name__ == "__main__":
    asyncio.run(main())

