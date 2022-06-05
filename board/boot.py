import board
import digitalio
import usb_cdc
import time
import supervisor
#  import storage


def blink(k, time_on=0.6, time_off=0.2, fast=False):
    if fast:
        time_on = time_off = 0.05
    for _ in range(k):
        led.value = True
        time.sleep(time_on)
        led.value = False
        time.sleep(time_off)


def setup():
    global switch, led
    switch = digitalio.DigitalInOut(board.GP16)
    switch.direction = digitalio.Direction.INPUT
    switch.pull = digitalio.Pull.UP
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT


def main():
    blink(4, fast=True)

    usb_cdc.enable(console=True, data=True)

    if not switch.value:
        pass
        #  usb_cdc.enable(console=True, data=True)
        #  storage.remount("/", switch.value)
    else:
        supervisor.disable_autoreload()


if __name__ == '__main__':
    setup()
    try:
        main()
    except:  # NOQA
        blink(20, fast=True)
