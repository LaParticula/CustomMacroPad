# CircuitPython
import board
import digitalio
import time
import usb_hid
import usb_cdc
import json

# Adafruit
from adafruit_hid.keyboard import Keyboard


def blink(k, time_on=0.5, time_off=0.2):
    for _ in range(k):
        led.value = True
        time.sleep(time_on)
        led.value = False
        time.sleep(time_off)


def reload_bindings():
    global keyboard_pins
    with open('bindings.json', 'r') as fp:
        data = json.load(fp)

    keyboard_pins = []
    for btn, keycode in data.items():
        if not keycode:
            continue
        pin = GP_PIN_PER_BTN[btn]
        keyboard_pins.append((pin, keycode))


def setup():
    global led, keyboard_pins, keyboard, uart, GP_PIN_PER_BTN
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT

    uart = usb_cdc.data
    uart.timeout = 0

    keyboard = Keyboard(usb_hid.devices)

    GP_PIN_PER_BTN = {
        "select": board.GP0,
        "cross": board.GP1,
        "left": board.GP2,
        "triangle": board.GP3,
        "down": board.GP4,
        "up": board.GP5,
        "square": board.GP6,
        "right": board.GP7,
        "circle": board.GP8,
        "start": board.GP9,
    }

    with open('bindings.json', 'r') as fp:
        data = json.load(fp)

    keyboard_pins = []
    for btn, keycode in data.items():
        pin = digitalio.DigitalInOut(GP_PIN_PER_BTN[btn])
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        GP_PIN_PER_BTN[btn] = pin
        if not keycode:
            continue
        keyboard_pins.append((pin, keycode))


def main():
    while True:
        if uart.in_waiting:
            data = uart.read(8)
            uart.reset_input_buffer()
            if data == b'rebind':
                reload_bindings()
                blink(1, 0.1, 0.1)

        for pin, keycode in keyboard_pins:
            if not pin.value:
                keyboard.press(keycode)
            else:
                keyboard.release(keycode)


if __name__ == '__main__':
    setup()
    try:
        main()
    except Exception as e:
        print(e)
