# Python
import os
import subprocess
import platform
import argparse
import string
import json
import curses
import time

# Pyserial
import serial
if platform.system() == 'Windows':
    import serial.tools.list_ports_windows
else:
    import serial.tools.list_ports_linux

# Pynput
from pynput.keyboard import Listener, Key

# App
from binding_tables import HID_KEY_CODES, BUTTON_NAMES


class BoardException(Exception):
    def print(self):
        for arg in self.args:
            print(arg)


class GetKeys(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        import ipdb; ipdb.set_trace()  # NOQA
        values = self._validate_and_normalize_input(*values)
        list_ = getattr(namespace, self.dest) or []
        if self.dest == 'bindings_to_remove':
            list_.extend(values)
        else:
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
            key = 'Unbinded'
        formatted_bindings[button] = key

    return formatted_bindings


def print_bindings(bindings):
    bindings = format_bindings(bindings)
    largest_btn_len = len(max(bindings.keys(), key=len))
    indentation = ' ' * 4
    print()
    print(indentation + 'BTN' + ' ' * largest_btn_len + 'KEY')
    print(indentation + '')
    for button, key in bindings.items():
        spaces = ' ' * (largest_btn_len - len(button)) + '   '
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


def validate_port_type(port):
    if OPERATING_SYSTEM == 'Linux':
        ports = serial.tools.list_ports_linux.comports()
    elif OPERATING_SYSTEM == 'Windows':
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


def on_press(key):
    global pressed_key
    if not pressed_key:
        if isinstance(key, Key):
            pressed_key = key.name
        elif key:
            pressed_key = key.char


def on_release(key):
    global released_key
    if not released_key:
        if isinstance(key, Key):
            released_key = key.name
        elif key:
            released_key = key.char


def custom_curses_wrapper(func, *args, **kwargs):
    try:
        key_listener = Listener(on_press, on_release)
        key_listener.start()
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        stdscr.refresh()
        return func(stdscr, *args, **kwargs)
    finally:
        if 'key_listener' in locals():
            key_listener.stop()
        if 'stdscr' in locals():
            stdscr.keypad(False)
            curses.echo()
            curses.nocbreak()
            curses.endwin()
        curses.flushinp()


class BindingWindow:
    def __init__(self, pos, key_pos, button, key):
        self.button = button
        self.key = key
        self.key_pos = key_pos
        self.win = curses.newwin(1, curses.COLS - 4, *pos)
        self.win.addstr(0, 1, button)
        self.change_key(key)

    def change_key(self, key, focus=False):
        self.win.addstr(0, self.key_pos, key)
        self.win.clrtoeol()
        if focus:
            self.focus(True)
        self.win.refresh()

    def focus(self, focus):
        if focus:
            self.win.chgat(0, 0, curses.A_REVERSE)
        else:
            self.win.chgat(0, 0, curses.A_NORMAL)
        self.win.refresh()


class BindingWinManager:
    def __init__(self, start_pos, bindings):
        self.current_pos = list(start_pos)
        self.current_win_index = 0
        self.is_binding = False
        self.prev_key = None
        self.bindings = bindings
        self.key_pos = len(max(bindings.keys(), key=len)) + 6

        self.bind_wins = []
        for button, key in format_bindings(bindings).items():
            win = BindingWindow(
                self.current_pos, self.key_pos, button, key
            )
            self.current_pos[0] += 1
            self.bind_wins.append(win)

        self.bind_wins[0].focus(True)

    def _get_current_window(self):
        return self.bind_wins[self.current_win_index]

    def enter_binding_mode(self):
        bind_win = self._get_current_window()
        bind_win.change_key('<Press any key>', focus=True)
        self.is_binding = True

    def exit_binding_mode(self):
        bind_win = self._get_current_window()
        bind_win.change_key(bind_win.key, focus=True)
        self.is_binding = False

    def rebind(self, key):
        self.is_binding = False
        bind_win = self._get_current_window()
        bind_win.change_key(key, focus=True)
        bind_win.key = key
        self.bindings[bind_win.button] = HID_KEY_CODES[key]
        if not args.dry_run:
            write_bindings(self.bindings)
            if args.reload:
                reload_bindings()

    def move_vertically(self, direction):
        self._get_current_window().focus(False)
        if direction == 'up':
            if self.current_win_index == 0:
                self.current_win_index = len(self.bind_wins) - 1
            else:
                self.current_win_index -= 1
        elif direction == 'down':
            if self.current_win_index == len(self.bind_wins) - 1:
                self.current_win_index = 0
            else:
                self.current_win_index += 1
        self._get_current_window().focus(True)


def run_interactive_mode(stdscr, bindings):
    global pressed_key, released_key

    stdscr = curses.initscr()
    curses.curs_set(0)
    top_msg = 'Use arrow keys to navigate, press Enter to bind.'
    stdscr.addstr(1, 2, top_msg)

    largest_btn = len(max(bindings, key=len))
    stdscr.addstr(3, 3, 'Buttons', curses.A_BOLD)
    stdscr.addstr(3, 8 + largest_btn, 'Keys', curses.A_BOLD)
    stdscr.refresh()
    binding_win_manager = BindingWinManager((5, 2), bindings)

    last_esc_time = None
    canceled_binding = False
    while True:
        pressed_key = released_key = None

        while not pressed_key:
            time.sleep(0.001)

        if binding_win_manager.is_binding:
            if pressed_key == 'esc':
                last_esc_time = time.time()
                while released_key != 'esc':
                    released_key = None
                    while not released_key:
                        if time.time() - last_esc_time > 1:
                            released_key = 'esc'
                            canceled_binding = True
                released_key = None
                if canceled_binding:
                    canceled_binding = False
                    binding_win_manager.exit_binding_mode()
                    while not released_key:
                        time.sleep(0.001)
                    continue
            binding_win_manager.rebind(pressed_key)

        elif pressed_key in ('enter', 'space'):
            binding_win_manager.enter_binding_mode()

        elif pressed_key in ('esc', 'q'):
            break

        elif pressed_key in ('up', 'k'):
            binding_win_manager.move_vertically('up')

        elif pressed_key in ('down', 'j'):
            binding_win_manager.move_vertically('down')


def write_bindings(bindings):
    with open(config_file_path, 'w') as fp:
        json.dump(bindings, fp, indent=4)


def get_board_serial():
    if args.port:
        if not os.path.exists(args.port):
            raise BoardException(
                'The specified port could not be found.'
            )
        port = args.port
    else:
        ports = serial.tools.list_ports_linux.comports()
        try:
            port = [
                port.device
                for port in sorted(ports)
                if port.serial_number
            ][-1]
        except IndexError:
            raise BoardException(
                'Board port could not be detected automatically.',
                'The bindings will not be reloaded on board.',
                'You must specify it manually with "--port" ' +
                'or you can avoid it with "--no-reload".'
            )

    board_serial = serial.Serial(
        port, baudrate=9600, timeout=0, parity=serial.PARITY_NONE,
    )
    return board_serial


def reload_bindings():
    global board_serial
    if not board_serial or board_serial.closed:
        board_serial = get_board_serial()
    board_serial.write(b'rebind')


def main():
    global config_file_path, args
    board_path = args.path if args.path else get_board_path()
    write = False
    config_file_path = board_path + 'bindings.json'
    bindings = get_bindings(config_file_path)

    if args.bindings:
        for button, key in args.bindings:
            bindings[button] = HID_KEY_CODES[key]
        write = True

    if args.bindings_to_remove:
        for button in args.bindings_to_remove:
            bindings[button] = None
        write = True

    if args.interactive:
        custom_curses_wrapper(run_interactive_mode, bindings)

    if not args.dry_run and (write or args.interactive):
        write_bindings(bindings)
        if args.reload:
            reload_bindings()

    if args.list:
        print_bindings(bindings)


def setup():
    global OPERATING_SYSTEM, args, released_key, pressed_key, board_serial
    OPERATING_SYSTEM = platform.system()
    board_serial = None
    pressed_key = None
    released_key = None
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
        '-i', '--interactive',
        action='store_true',
        help='start in interactive binding mode'
    )
    arg_parser.add_argument(
        '-b', '--bind',
        action=GetKeys,
        nargs=2,
        metavar=('BTN', 'KEY'),
        dest='bindings',
        help='bind a pad button with a keyboard key'
    )
    arg_parser.add_argument(
        '-r', '--remove',
        action=GetKeys,
        nargs='+',
        metavar='BTN',
        dest='bindings_to_remove',
        help='remove a pad button binding'
    )
    arg_parser.add_argument(
        '-n', '--no-reload',
        action='store_false',
        dest='reload',
        help='do not reload board bindings'
    )
    arg_parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='list all bindings'
    )
    arg_parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='execute without writing on board disk'
    )
    arg_parser.add_argument(
        '-f', '--path',
        metavar='PATH',
        type=validate_path_type,
        help='specify a path to the mounted board'
    )
    arg_parser.add_argument(
        '-p', '--port',
        metavar='PORT',
        type=validate_port_type,
        help='specify the port for the programmable board'
    )
    args = arg_parser.parse_args()


if __name__ == '__main__':
    setup()
    try:
        main()
    except BoardException as e:
        e.print()
    finally:
        if board_serial:
            board_serial.close()
