# Based on:
    # https://github.com/kevinmcaleer/burgerbot/blob/main/bluetooth_burgerbot.py
    # Bluetooth Remote Control
    # Kevin McAleer
    # KevsRobot.com

import aioble
import bluetooth
import uasyncio as asyncio
import os


# Bluetooth UUIDS can be found online at https://www.bluetooth.com/specifications/gatt/services/
_REMOTE_UUID = bluetooth.UUID(0x1812)
_REMOTE_CHARACTERISTICS_UUID = bluetooth.UUID(0x2a4d)


input_state = {
    'left_x': 0,
    'left_y': 0,
    'right_x': 0,
    'right_y': 0,
    'left_stick': False,
    'right_stick': False,
    'left_trig': 0,
    'right_trig': 0,
    'left_bump': False,
    'right_bump': False,
    'dpad_up': False,
    'dpad_down': False,
    'dpad_left': False,
    'dpad_right': False,
    'a': False,
    'b': False,
    'x': False,
    'y': False,
    'menu': False,
    'view': False,
}


async def find_remote():
    # Clear past connection data
    aioble.stop()

    # Remove existing pair data to prevent issues when pairing, this is not a great solution
    try:
        os.remove("ble_secrets.json")
    except:
        pass

    # Scan for 5 seconds, in active mode, with very low interval/window (to maximise detection rate).
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            # See if it matches the name of our controller
            if result.name() == "Xbox Wireless Controller":
                print("Found Xbox Wireless Controller")
                # print(result.services())
                # for item in result.services():
                #     print (item)
                return result.device
    return None


def map_range(x, in_min, in_max, out_min, out_max):
    return float((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


async def parse_HID_report(HID_report):
    input_state.update(
        left_x = map_range(int.from_bytes(HID_report[0:2],'little'),0,65535,-1.0,1.0),
        left_y = map_range(int.from_bytes(HID_report[2:4],'little'),0,65535,-1.0,1.0),
        right_x = int.from_bytes(HID_report[4:6],'little'),
        right_y = int.from_bytes(HID_report[6:8],'little'),
        a = bool(HID_report[13:14][0] & 0b00001),
        b = bool(HID_report[13:14][0] & 0b00010),
        x = bool(HID_report[13:14][0] & 0b01000),
        y = bool(HID_report[13:14][0] & 0b10000),
        left_bump = bool(HID_report[13:14][0] & 0b01000000),
        right_bump = bool(HID_report[13:14][0] & 0b10000000),
        view = bool(HID_report[14:15][0] & 0b0000100),
        menu = bool(HID_report[14:15][0] & 0b0001000),
        dpad_up = bool(HID_report[12:13][0] == 0b1),
        dpad_down = bool(HID_report[12:13][0] == 0b101),
        dpad_left = bool(HID_report[12:13][0] == 0b111),
        dpad_right = bool(HID_report[12:13][0] == 0b11),
        left_trig = int.from_bytes(HID_report[8:10], 'little'),
        right_trig = int.from_bytes(HID_report[10:12], 'little')
    )
    return None


async def controller_task():
    while True:
        print('starting controller task')
        device = await find_remote()

        if not device:
            print("Robot Remote not found")
            continue

        try:
            print("Connecting to", device)
            connection = await device.connect(timeout_ms=2000)

            try:
                await connection.pair(bond=True, le_secure=False, mitm=False, timeout_ms=2000)
            except Exception as e:
                print(f'Error when pairing; {e}')
                continue

        except asyncio.TimeoutError:
            print("Timeout during connection")
            continue

        async with connection:
            print("Connected")

            robot_service = await connection.service(_REMOTE_UUID)

            try:
                # Read from 0x2a4b to bring the controller out of pair mode
                # from https://github.com/pybricks/pybricks-micropython/blob/master/pybricks/iodevices/pb_type_iodevices_xbox_controller.c#L59
                pair_characteristic = await robot_service.characteristic(bluetooth.UUID(0x2a4b))
                print("Reading pair_characteristic")
                await pair_characteristic.read(timeout_ms=1000)
                print("Done reading pair_characteristic")
            except Exception as e:
                    print(f'Something went wrong when reading pair_characteristic; {e}')

            HID_report_characteristic = await robot_service.characteristic(_REMOTE_CHARACTERISTICS_UUID)
            print("Subscribing to characteristic")
            await HID_report_characteristic.subscribe(notify=True)

            while True:
                try:
                    if robot_service == None:
                        print('Remote disconnected')
                        break
                except asyncio.TimeoutError:
                    print("Timeout discovering services/characteristics")
                    break

                if HID_report_characteristic == None:
                    print('No control')
                    break

                try:
                    while True:
                        HID_report = await HID_report_characteristic.notified()
                        await parse_HID_report(HID_report)
                        print(input_state['left_x'],input_state['left_y'])
                except Exception as e:
                    print(f'Something went wrong; {e}')
                    break

            await connection.disconnected()
            print('Remote disconnected')

                
async def main():
    tasks = [
        asyncio.create_task(controller_task()),
    ]
    await asyncio.gather(*tasks)


try:
    while True:
        asyncio.run(main())
except KeyboardInterrupt:
    print('Got keyboard interrupt')
finally:
    print('Done shutting down controller')