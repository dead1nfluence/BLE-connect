import asyncio
import json
import time
import locale
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

# Store subscribed characteristics
subscribed_chars = set()

def notification_handler(sender, data):
    """Handle incoming notifications from subscribed characteristics"""
    print(f"[Notification] From {sender}: {data.decode(errors='ignore')}")

def print_scan_help():
    """Display help menu for device scanning"""
    print("\nScanning commands:")
    print("  <number>                - Select a device to connect to (e.g., 0, 1, ...)")
    print("  help                    - Display this help message")
    print("  refresh                 - Re-scan for nearby BLE devices")
    print("  exit                    - Exit the script (same as quit)")
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
                choice = input("Select device to connect to (number) or enter a command: ").strip().lower()
                if choice == "help":
                    print_scan_help()
                elif choice in ("quit", "exit"):
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

def list_available_characteristics(client):
    """List all characteristics, numbering those with read, notify, or indicate"""
    print("\n[+] Available GATT Services and Characteristics:")
    actionable_chars = []
    char_index = 0
    for service in client.services:
        print(f" [Service] {service.uuid}")
        for char in service.characteristics:
            props = ', '.join(char.properties)
            if 'read' in char.properties or 'notify' in char.properties or 'indicate' in char.properties:
                print(f" └── [{char_index}] {char.uuid} ({props})")
                actionable_chars.append((char.uuid, char.properties))
                char_index += 1
            else:
                print(f" └── {char.uuid} ({props})")
    if not actionable_chars:
        print("[-] No characteristics with read, notify, or indicate properties found.")
    else:
        print(f"[*] {char_index} actionable characteristics listed above (use for read/subscribe).")
    print()
    return actionable_chars

async def read_characteristic_by_index(client, index, actionable_chars):
    """Read from a characteristic by its index"""
    if not actionable_chars:
        print("[-] No readable characteristics available. Use 'list' to view characteristics.")
        return
    if not isinstance(index, int) or index < 0 or index >= len(actionable_chars):
        print("[-] Invalid characteristic number. Available characteristics:")
        list_available_characteristics(client)
        return
    uuid, props = actionable_chars[index]
    if 'read' not in props:
        print(f"[-] Characteristic {uuid} does not support read")
        return
    try:
        value = await client.read_gatt_char(uuid)
        print(f"[<] Read from {uuid}: {value.decode(errors='ignore')}")
    except Exception as e:
        print(f"[-] Error reading from {uuid}: {e}")

async def subscribe_to_characteristic_by_index(client, index, actionable_chars):
    """Subscribe to a characteristic by its index"""
    if not actionable_chars:
        print("[-] No subscribable characteristics available. Use 'list' to view characteristics.")
        return
    if not isinstance(index, int) or index < 0 or index >= len(actionable_chars):
        print("[-] Invalid characteristic number. Available characteristics:")
        list_available_characteristics(client)
        return
    uuid, props = actionable_chars[index]
    if 'notify' not in props and 'indicate' not in props:
        print(f"[-] Characteristic {uuid} does not support notify or indicate")
        return
    try:
        await client.start_notify(uuid, notification_handler)
        subscribed_chars.add(uuid.lower())
        print(f"[*] Subscribed to {uuid}")
    except Exception as e:
        print(f"[-] Error subscribing to {uuid}: {e}")

def print_help():
    """Display available commands and their format"""
    print("\nAvailable commands:")
    print("  help                    - Display this help message")
    print("  list                    - List all characteristics with numbered actionable ones")
    print("  subscribe <number>      - Subscribe to a numbered characteristic (notify/indicate)")
    print("  read <number>           - Read value from a numbered characteristic")
    print("  exit                    - Disconnect from the device (same as quit)")
    print("  rescan                  - Disconnect and return to device scan")
    print("\nExample: read 0, subscribe 1")
    print()

async def interact_with_device(address):
    try:
        async with BleakClient(address, timeout=10.0) as client:
            print("[*] Connected to", address)
            # List all characteristics, numbering actionable ones
            actionable_chars = list_available_characteristics(client)
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

                    elif command == "rescan":
                        # Unsubscribe from all characteristics before disconnecting
                        for char_uuid in subscribed_chars.copy():
                            try:
                                await client.stop_notify(char_uuid)
                                subscribed_chars.remove(char_uuid)
                                print(f"[*] Unsubscribed from {char_uuid}")
                            except Exception as e:
                                print(f"[-] Error unsubscribing from {char_uuid}: {e}")
                        print("[*] Disconnecting to rescan...")
                        return False  # Return False to trigger rescan

                    elif command == "help":
                        print_help()

                    elif command == "list":
                        list_available_characteristics(client)

                    elif command == "subscribe":
                        if len(parts) != 2 or not parts[1].isdigit():
                            print("[-] Invalid format. Use: subscribe <number>")
                            list_available_characteristics(client)
                        else:
                            index = int(parts[1])
                            await subscribe_to_characteristic_by_index(client, index, actionable_chars)

                    elif command == "read":
                        if len(parts) != 2 or not parts[1].isdigit():
                            print("[-] Invalid format. Use: read <number>")
                            list_available_characteristics(client)
                        else:
                            index = int(parts[1])
                            await read_characteristic_by_index(client, index, actionable_chars)

                    else:
                        print("[-] Invalid command. Type 'help' for commands.")

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
