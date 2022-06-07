# Python
import os
import subprocess
import platform
import argparse
import string
import json

# Pynput
from pynput.keyboard import Listener, Key

# App
from binding_tables import HID_KEY_CODES, BUTTON_NAMES


class GetKeys(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        values = self._validate_and_normalize_input(*values)
        list_ = getattr(namespace, self.dest) or []
        list_.append(values)
        setattr(namespace, self.dest, list_)

    def _validate_and_normalize_input(self, button, key=None):
        try:
            button = BUTTON_NAMES[int(button)]
        except ValueError:
            button = button.lower().replace(' ', '_')
        except KeyError:
            pass

        if button not in BUTTON_NAMES.values():
            msg = f'{self.metavar[0]} does not match any existing button.'
            raise argparse.ArgumentError(self, msg)

        if key:
            key = key.lower().replace(' ', '_')
            if key not in HID_KEY_CODES:
                msg = f'{self.metavar[1]} does not match any existing key.'
                raise argparse.ArgumentError(self, msg)
            return (button, key)

        return button


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


def get_root(request=True):
    test_cmd = 'sudo -n echo > /dev/null'
    output = subprocess.getoutput(test_cmd)
    if output.startswith('sudo'):
        if not request:
            return False
        test_cmd = 'sudo echo > /dev/null'
        print('Requesting root access. <Ctrl+C> to cancel.')
        try:
            output = subprocess.getoutput(test_cmd)
        except KeyboardInterrupt:
            return False
        return not output.startswith('sudo')
    else:
        return True


def get_board_path():
    if OPERATING_SYSTEM == 'Linux':
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
            print('No programmable board with a file system was detected.')
            return
        device_path = output.strip().rsplit(' ')[0]

        cmd = f'udisksctl mount -b {device_path}'
        exit_code, output = subprocess.getstatusoutput(cmd)
        # sample: 'Mounted /dev/sdc1 at /media/$USER/CIRCUITPY.'
        if exit_code == 0:
            board_path = output.rsplit(' ', 1)[1][:-1] + '/'
            return board_path
        else:
            print(output)
            return

    elif OPERATING_SYSTEM == 'Windows':
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
            print(
                'No programmable board with a mounted ' +
                'file system was detected.'
            )
            return
        board_path = partition_letter[0] + ':\\'
        return board_path
    else:
        print('Board path auto-detect is not supported for this OS.')
        print('You must specify it with "--path PATH".')
        return


def print_bindings(bindings):
    longest_button_length = 0
    for button in bindings.keys():
        if len(button) > longest_button_length:
            longest_button_length = len(button)

    indentation = ' ' * 4
    print()
    print(indentation + 'BTN' + ' ' * (longest_button_length) + 'KEY')
    print(indentation + '')
    for button, key in bindings.items():
        if key:
            key = [
                key_str
                for key_str in HID_KEY_CODES.keys()
                if key == HID_KEY_CODES[key_str]
            ][0].replace('_', ' ')
        else:
            key = 'Unbinded'
        spaces = ' ' * (longest_button_length - len(button)) + '   '
        print(indentation + button + spaces + key)
    print()


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


def validate_path_type(path):
    if OPERATING_SYSTEM == 'Linux':
        if not path.endswith('/'):
            path += '/'
    elif OPERATING_SYSTEM == 'Windows':
        if not path.endswith('\\'):
            path += '\\'

    if not os.path.exists(path):
        msg = 'Specified path does not exists.'
        raise argparse.ArgumentTypeError(msg)

    return path


def main():
    args = arg_parser.parse_args()
    if args.path:
        board_path = args.path
    else:
        board_path = get_board_path()
        if not board_path:
            return

    config_file_path = board_path + 'bindings.json'
    bindings = get_bindings(config_file_path)

    if args.bindings:
        for button, key in args.bindings:
            bindings[button] = HID_KEY_CODES[key]

    if args.bindings_to_remove:
        for button in args.bindings_to_remove:
            bindings[button] = None

    if not args.dry_run:
        with open(config_file_path, 'w') as fp:
            json.dump(bindings, fp, indent=4)

    if args.list:
        print_bindings(bindings)


def setup():
    global OPERATING_SYSTEM, arg_parser
    OPERATING_SYSTEM = platform.system()
    arg_parser = argparse.ArgumentParser(
        description="""\
            Create a config file of bindings between\
            virtual buttons and keyboard HID codes\
            and save it on programmable boards with\
            a mountable file system,\
            like MicroPython or CircuitPython boards.
        """,
        formatter_class=CustomHelpFormatter
    )
    arg_parser.add_argument(
        '-b', '--bind',
        action=GetKeys,
        nargs=2,
        metavar=('BTN', 'KEY'),
        dest='bindings',
        help='Bind a pad button with a keyboard key.'
    )
    arg_parser.add_argument(
        '-r', '--remove',
        action=GetKeys,
        nargs=1,
        metavar='BTN',
        dest='bindings_to_remove',
        help='Remove a pad button binding.'
    )
    arg_parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List all bindings.'
    )
    arg_parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Execute without writing on board disk.'
    )
    arg_parser.add_argument(
        '-p', '--path',
        metavar='PATH',
        type=validate_path_type,
        help='Specify a path to the mounted board.'
    )


if __name__ == '__main__':
    setup()
    main()
