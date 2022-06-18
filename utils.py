# Python
import os
import subprocess
import platform
import argparse
import string
import json

# Pyserial
import serial
if platform.system() == 'Windows':
    import serial.tools.list_ports_windows as list_ports
else:
    import serial.tools.list_ports_linux as list_ports

# App
from binding_tables import HID_KEY_CODES, BUTTON_NAMES


class BoardException(Exception):
    def print(self):
        for arg in self.args:
            print(arg)


class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar
        else:
            parts = []
            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)

            # if the Optional takes a value, format is:
            #    -s, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)
                parts = action.option_strings[:]
                parts[-1] += ' ' + args_string

            return ', '.join(parts)


def get_board_path():
    OS = platform.system()
    if OS == 'Linux':
        cmd = 'findmnt -lo SOURCE,LABEL,TARGET | grep CIRCUITPY'
        output = subprocess.getoutput(cmd)
        #  sample: '/dev/sdc1             /media/$USER/CIRCUITPY'
        #  sample: '/dev/sdd1   CIRCUITPY /media/$USER/CIRCUITPY'
        for output_line in output.split('\n'):
            new_data = [
                data
                for data in output_line.strip().split(' ')
                if data
            ]
            if len(new_data) == 3:
                board_path = new_data[-1] + '/'
                return board_path

        cmd = 'lsblk -o PATH,LABEL | grep CIRCUITPY'
        output = subprocess.getoutput(cmd)
        #  sample: '/dev/sdc1   CIRCUITPY'
        if not output:
            raise BoardException(
                'No programmable board with ' +
                'a file system was detected.'
            )
        device_path = output.strip().rsplit(' ')[0]

        cmd = f'udisksctl mount -b {device_path}'
        exit_code, output = subprocess.getstatusoutput(cmd)
        # sample: 'Mounted /dev/sdc1 at /media/$USER/CIRCUITPY.'
        if exit_code != 0:
            raise BoardException(output)

        board_path = output.rsplit(' ', 1)[1][:-1] + '/'
        return board_path

    elif OS == 'Windows':
        import win32api
        #  sample: ['F']
        partition_letter = [
            char
            for char in string.ascii_uppercase
            if (
                os.path.exists(char + ':/') and
                win32api.GetVolumeInformation(char + ':/')[0] == 'CIRCUITPY'
            )
        ]
        if not partition_letter:
            raise BoardException(
                'No programmable board with a mounted ' +
                'file system was detected.'
            )
        board_path = partition_letter[0] + ':\\'
        return board_path
    else:
        raise BoardException(
            'Board path auto-detect is not supported for this OS.',
            'You must specify it with "--path PATH".'
        )


def format_bindings(bindings):
    formatted_bindings = bindings.copy()
    for button, key in bindings.items():
        if key:
            key = [
                key_str
                for key_str in HID_KEY_CODES.keys()
                if key == HID_KEY_CODES[key_str]
            ][0].replace('_', ' ')
        else:
            #  key = 'Unbinded'
            key = '--'
        formatted_bindings[button] = key

    return formatted_bindings


def get_bindings(config_file_path):
    if os.path.exists(config_file_path):
        with open(config_file_path, 'r') as fp:
            bindings = json.load(fp)

        for button in bindings.copy().keys():
            if button not in BUTTON_NAMES.values():
                del bindings[button]

        for button in BUTTON_NAMES.values():
            if button not in bindings:
                bindings[button] = None

    else:
        bindings = {
            button: None
            for button in BUTTON_NAMES.values()
        }

    return bindings


def validate_button_type(button):
    msg = f'\'{button}\' does not match any existing button.'
    try:
        button = int(button)
    except ValueError:
        button = button.lower().replace(' ', '_')

    if isinstance(button, int):
        if button not in BUTTON_NAMES.keys():
            raise argparse.ArgumentTypeError(msg)
        return BUTTON_NAMES[button]

    elif button not in BUTTON_NAMES.values():
        raise argparse.ArgumentTypeError(msg)

    return button


class ValidateBindingAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            button = validate_button_type(values[0])
        except argparse.ArgumentTypeError as e:
            raise argparse.ArgumentError(self, e)

        key = values[1].lower().replace(' ', '_')

        if key not in HID_KEY_CODES:
            msg = f'\'{key}\' does not match any existing key.'
            raise argparse.ArgumentError(self, msg)

        list_ = getattr(namespace, self.dest) or []
        list_.append((button, key))
        setattr(namespace, self.dest, list_)


def validate_path_type(path):
    if platform.system() == 'Windows':
        if not path.endswith('\\'):
            path += '\\'
    else:
        if not path.endswith('/'):
            path += '/'

    if not os.path.exists(path):
        msg = 'Specified path does not exists.'
        raise argparse.ArgumentTypeError(msg)

    return path


def validate_port_type(port):
    OS = platform.system()
    if OS == 'Linux':
        ports = serial.tools.list_ports_linux.comports()
    elif OS == 'Windows':
        ports = serial.tools.list_ports_windows.comports()
    else:
        raise BoardException(
            'This operating system does not support ' +
            'automatic port detection.',
            'You must specify it with "--port".'
        )
    ports = [port.device for port in sorted(ports)]

    if port not in ports:
        msg = 'Specified port is not found.'
        raise argparse.ArgumentTypeError(msg)

    return port


def get_board_serial(port):
    if port:
        if not os.path.exists(port):
            raise BoardException(
                'The specified port could not be found.'
            )
        port = port
    else:
        if platform.system() not in ('Windows', 'Linux'):
            raise BoardException(
                'Your operting system does not support port auto-detect.'
                'You must specify it manually with "--port" ' +
                'or you can avoid it with "--no-reload".'
            )
        ports = list_ports.comports()
        try:
            port = [
                port.device
                for port in sorted(ports)
                if port.serial_number
            ][-1]
        except IndexError:
            raise BoardException(
                'Board port could not be detected automatically.',
                'You must specify it manually with "--port" ' +
                'or you can avoid it with "--no-reload".'
            )

    board_serial = serial.Serial(
        port, baudrate=9600, timeout=0, parity=serial.PARITY_NONE,
    )
    return board_serial
