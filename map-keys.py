#!/usr/bin/env python

# Python
import argparse
import json
import curses
import time

# Pynput
from pynput.keyboard import Listener, Key

# App
from binding_tables import HID_KEY_CODES, BUTTON_NAMES
from utils import (
    BoardException,
    CustomHelpFormatter,
    format_bindings,
    get_board_path,
    get_board_serial,
    get_bindings,
    validate_button_type,
    validate_path_type,
    validate_port_type,
    ValidateBindingAction,
)


def print_bindings(bindings):
    bindings = format_bindings(bindings)
    btn_n_col_len = len(str(max(BUTTON_NAMES.keys())))
    btn_col_len = len(max(bindings.keys(), key=len))
    indent = ' ' * 4
    BOLD = '\033[1m'
    NORMAL = '\033[0m'
    header = '{}{}N{}Buttons{}Keys{}'.format(
        BOLD,
        indent,
        ' ' * (btn_n_col_len + 1),
        ' ' * (btn_col_len - 5),
        NORMAL
    )

    binding_lines = []
    for button, key in bindings.items():
        button_n = [
            num
            for num in BUTTON_NAMES.keys()
            if BUTTON_NAMES[num] == button
        ][0]
        binding_lines.append((
            '{}{}{}{}{}{}'.format(
                indent,
                button_n,
                ' ' * (btn_n_col_len - len(str(button_n)) + 2),
                button,
                ' ' * (btn_col_len - len(button) + 2),
                key
            ),
            button_n
        ))
    binding_lines = sorted(binding_lines, key=lambda line: line[1])

    print()
    print(header)  # '    N   Buttons   Keys'
    print()
    for line, _ in binding_lines:
        print(line)
    print()


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
            self.focus()
        self.win.refresh()

    def focus(self):
        self.win.chgat(0, 0, curses.A_REVERSE)
        self.win.refresh()

    def unfocus(self):
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

        self.bind_wins[0].focus()

    def _get_current_window(self):
        new_win_index = self.current_win_index % len(self.bind_wins)
        return self.bind_wins[new_win_index]

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
        bind_win.key = key
        self.bindings[bind_win.button] = HID_KEY_CODES[key]
        if not args.dry_run and not args.write_on_exit:
            write_bindings(self.bindings)
            if args.reload:
                reload_bindings()
        bind_win.change_key(key, focus=True)

    def move_vertically(self, direction):
        self._get_current_window().unfocus()
        if direction == 'up':
            self.current_win_index -= 1
        elif direction == 'down':
            self.current_win_index += 1
        self._get_current_window().focus()


def run_interactive_mode(stdscr, bindings):
    global pressed_key, released_key

    stdscr = curses.initscr()
    curses.curs_set(0)

    top_msg = 'Use arrow keys to navigate, press Enter to bind.'
    largest_btn = len(max(bindings, key=len))

    stdscr.addstr(1, 2, top_msg)
    stdscr.addstr(3, 3, 'Buttons', curses.A_BOLD)
    stdscr.addstr(3, 8 + largest_btn, 'Keys', curses.A_BOLD)
    stdscr.refresh()

    binding_win_manager = BindingWinManager((5, 2), bindings)

    last_esc_time = None
    canceled_binding = False
    while True:
        pressed_key = released_key = None

        while not pressed_key:
            pass

        if binding_win_manager.is_binding:
            if pressed_key == 'esc':  # if esc is pressed or held
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
                        pass
                    continue
            binding_win_manager.rebind(pressed_key)

        elif pressed_key in ('enter', 'space', 'r'):
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


def reload_bindings():
    global board_serial
    if not board_serial or board_serial.closed:
        board_serial = get_board_serial(args.port)
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

    if args.clear:
        bindings = {
            button: None
            for button in BUTTON_NAMES.values()
        }

    if args.interactive:
        custom_curses_wrapper(run_interactive_mode, bindings)

    if not args.dry_run and (write or args.interactive):
        write_bindings(bindings)
        if args.reload:
            reload_bindings()

    if args.list:
        print_bindings(bindings)


def setup():
    global args, board_serial, released_key, pressed_key
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
    binding_group = arg_parser.add_argument_group('binding')
    binding_group.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='start in interactive binding mode'
    )
    binding_group.add_argument(
        '-b', '--bind',
        action=ValidateBindingAction,
        nargs=2,
        metavar=('BTN', 'KEY'),
        dest='bindings',
        help='bind a pad button with a keyboard key'
    )
    binding_group.add_argument(
        '-c', '--clear',
        action='store_true',
        help='clear all bindings'
    )
    binding_group.add_argument(
        '-r', '--remove',
        type=validate_button_type,
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
        '-e', '--write-on-exit',
        action='store_true',
        help='write on disk only at the end of the program (-i)'
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
