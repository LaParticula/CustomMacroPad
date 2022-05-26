# CircuitPython
import board
import digitalio
import time
import usb_hid

# Adafruit
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode


def setup():
    global led, keyboard_pins, keyboard
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT
    keyboard = Keyboard(usb_hid.devices)
    GP_PIN_CODE_PAIRS = (
        (board.GP0, Keycode.W),
        (board.GP1, Keycode.A),
        (board.GP4, Keycode.S),
        (board.GP5, Keycode.D)
    )
    keyboard_pins = []
    for gp_pin, keycode in GP_PIN_CODE_PAIRS:
        pin = digitalio.DigitalInOut(gp_pin)
        pin.direction = digitalio.Direction.INPUT
        pin.pull = digitalio.Pull.UP
        keyboard_pins.append((pin, keycode))


def main():
    led.value = True
    time.sleep(0.5)
    led.value = False

    while True:
        #  if not keyboard_pins[0].value:
            #  led.value = True
            #  keyboard.press(Keycode.A)
            #  while not keyboard_pins[0].value:
                #  pass
            #  led.value = False
            #  keyboard.release(Keycode.A)
        for pin, keycode in keyboard_pins:
            if not pin.value:
                led.value = True
                keyboard.press(keycode)
            else:
                led.value = False
                keyboard.release(keycode)


if __name__ == '__main__':
    setup()
    main()
