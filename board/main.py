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
        "start": board.GP1,
        "cross": board.GP2,
        "up": board.GP3,
        "circle": board.GP4,
        "left": board.GP5,
        "right": board.GP6,
        "triangle": board.GP7,
        "down": board.GP8,
        "square": board.GP9
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
    blink(3)
    blink(1, 1, 0)

    while True:
        if uart.connected:
            data = uart.read(8)
            uart.reset_input_buffer()
            if data == b'rebind':
                reload_bindings()
                blink(10, 0.1, 0.1)

        for pin, keycode in keyboard_pins:
            if not pin.value:
                #  led.value = True
                keyboard.press(keycode)
            else:
                #  led.value = False
                keyboard.release(keycode)


if __name__ == '__main__':
    setup()
    main()
