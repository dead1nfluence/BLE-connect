import asyncio
import json
import time
import locale
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

# Store subscribed characteristics
subscribed_chars = set()

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
    """Handle incoming notifications from subscribed characteristics"""
    print(f"[Notification] From {sender}: {data.decode(errors='ignore')}")

def print_scan_help():
    """Display help menu for device scanning"""
    print("\nScanning commands:")
    print("  <number>                - Select a device to connect (e.g., 0, 1, ...)")
    print("  help                    - Display this help message")
    print("  refresh                 - Re-scan for nearby BLE devices")
    print("  quit                    - Exit the script")
    print()

async def scan_for_ble():
    while True:
        print("Scanning for nearby BLE devices (5s)...")
        devices = await BleakScanner.discover(timeout=5.0)
        if not devices:
            print("[-] No devices found.")
        else:
            # Display numbered list
            for i, device in enumerate(devices):
                name = device.name or "Unknown"
                print(f"[{i}] {name} ({device.address})")
        
        while True:
            try:
                choice = input("Select device to connect (number) or command: ").strip().lower()
                if choice == "help":
                    print_scan_help()
                elif choice == "quit":
                    print("[-] Exiting script.")
                    return None
                elif choice == "refresh":
                    break  # Break inner loop to re-scan
                elif choice.isdigit():
                    index = int(choice)
                    if 0 <= index < len(devices):
                        return devices[index].address
                    else:
                        print("[-] Invalid device number. Try again.")
                else:
                    print("[-] Invalid input. Type 'help' for options.")
            except KeyboardInterrupt:
                print("\n[-] Exiting script.")
                return None

def print_available_characteristics(client):
    """Display available GATT services and characteristics"""
    print("\n[+] Available GATT Services and Characteristics:")
    for service in client.services:
        print(f" [Service] {service.uuid}")
        for char in service.characteristics:
            props = ', '.join(char.properties)
            print(f" └── [Char] {char.uuid} ({props})")
    print()

async def subscribe_to_characteristic(client, char_uuid):
    """Subscribe to a characteristic if it supports notify or indicate"""
    try:
        for service in client.services:
            for char in service.characteristics:
                if char.uuid.lower() == char_uuid.lower():
                    if 'notify' in char.properties or 'indicate' in char.properties:
                        await client.start_notify(char_uuid, notification_handler)
                        subscribed_chars.add(char_uuid.lower())
                        print(f"[*] Subscribed to {char_uuid}")
                        return True
                    else:
                        print(f"[-] Characteristic {char_uuid} does not support notify or indicate")
                        return False
        print(f"[-] Characteristic {char_uuid} not found")
        return False
    except Exception as e:
        print(f"[-] Error subscribing to {char_uuid}: {e}")
        return False

async def read_characteristic(client, char_uuid):
    """Read from a characteristic if it supports read"""
    try:
        for service in client.services:
            for char in service.characteristics:
                if char.uuid.lower() == char_uuid.lower():
                    if 'read' in char.properties:
                        value = await client.read_gatt_char(char_uuid)
                        print(f"[<] Read from {char_uuid}: {value.decode(errors='ignore')}")
                        return True
                    else:
                        print(f"[-] Characteristic {char_uuid} does not support read")
                        return False
        print(f"[-] Characteristic {char_uuid} not found")
        return False
    except Exception as e:
        print(f"[-] Error reading from {char_uuid}: {e}")
        return False

def print_help():
    """Display available commands and their format"""
    print("\nAvailable commands:")
    print("  help                    - Display this help message")
    print("  subscribe <UUID>        - Subscribe to notifications from a characteristic")
    print("  read <UUID>             - Read value from a characteristic")
    print("  quit                    - Disconnect from the device")
    print("  exit                    - Disconnect from the device (same as quit)")
    print("\nExample UUID format: 00002a00-0000-1000-8000-00805f9b34fb")
    print()

async def interact_with_device(address):
    try:
        async with BleakClient(address, timeout=10.0) as client:
            print("[*] Connected to", address)
            # Print all available characteristics right after connection
            print_available_characteristics(client)  # Removed 'await' since function is not async
            print("Successfully connected. Type 'help' for commands.")
            
            while True:
                try:
                    user_input = input("> ").strip().lower()
                    if not user_input:
                        continue
                        
                    parts = user_input.split()
                    command = parts[0] if parts else ""

                    if command in ("quit", "exit"):
                        # Unsubscribe from all characteristics before disconnecting
                        for char_uuid in subscribed_chars.copy():
                            try:
                                await client.stop_notify(char_uuid)
                                subscribed_chars.remove(char_uuid)
                                print(f"[*] Unsubscribed from {char_uuid}")
                            except Exception as e:
                                print(f"[-] Error unsubscribing from {char_uuid}: {e}")
                        break

                    elif command == "help":
                        print_help()

                    elif command == "subscribe" and len(parts) == 2:
                        char_uuid = parts[1]
                        await subscribe_to_characteristic(client, char_uuid)

                    elif command == "read" and len(parts) == 2:
                        char_uuid = parts[1]
                        await read_characteristic(client, char_uuid)

                    else:
                        print("[-] Invalid command. Type 'help' for available commands.")

                except KeyboardInterrupt:
                    print("\n[*] Disconnecting...")
                    # Unsubscribe from all characteristics
                    for char_uuid in subscribed_chars.copy():
                        try:
                            await client.stop_notify(char_uuid)
                            subscribed_chars.remove(char_uuid)
                            print(f"[*] Unsubscribed from {char_uuid}")
                        except Exception as e:
                            print(f"[-] Error unsubscribing from {char_uuid}: {e}")
                    break
                except Exception as e:
                    print(f"[-] Error: {e}")

            print("Disconnected.")
            return True
    except asyncio.TimeoutError:
        print("timeout")
        return False
    except BleakError as e:
        print(f"[-] Connection error: {e}")
        return False

async def main():
    while True:
        address = await scan_for_ble()
        if not address:
            break  # Exit if user quits or aborts during device selection
        success = await interact_with_device(address)
        if success:
            break  # Exit loop if connection was successful
        print("Returning to device selection...")

if __name__ == "__main__":
    asyncio.run(main())
