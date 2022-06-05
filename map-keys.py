# Python
import os
import subprocess
import platform
import argparse
if platform.system() == 'Windows':
    import win32api

# Pynput
from pynput.keyboard import Listener, Key

# App
from binding_tables import HID_KEY_CODES, BUTTON_NAMES


class GetKeys(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        pad_btn, key = values
        key = key.lower()
        try:
            pad_btn = BUTTON_NAMES[int(pad_btn)]
        except ValueError:
            pad_btn = pad_btn.lower()
        except KeyError:
            pass

        if pad_btn not in BUTTON_NAMES.values():
            msg = f'{self.metavar[0]} does not match any existing button.'
            raise argparse.ArgumentError(self, msg)

        if key not in HID_KEY_CODES:
            msg = f'{self.metavar[1]} does not match any existing key.'
            raise argparse.ArgumentError(self, msg)

        bindings = getattr(namespace, self.dest) or []
        bindings.append((pad_btn, key))
        setattr(namespace, self.dest, bindings)


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


def get_board_path(retry=False):
    if platform.system() == 'Linux':
        has_root = get_root(request=False)

        #  sample: '/dev/sdc1             /media/$USER/CIRCUITPY'
        #  sample: '/dev/sdd1   CIRCUITPY /media/$USER/CIRCUITPY'
        mount_data = subprocess.getoutput(
            'findmnt -lo SOURCE,LABEL,TARGET | grep CIRCUITPY'
        )
        board_path = None
        if mount_data:
            folders_to_unmount = []
            for data_line in mount_data.split('\n'):
                new_data = [
                    data
                    for data in data_line.strip().split(' ')
                    if data
                ]
                if len(new_data) == 3:
                    board_path = new_data[-1]
                elif not retry:
                    folders_to_unmount.append(new_data[-1])

            if folders_to_unmount:
                print('There\'re folders mounted on disconnected devices.')
                for path in folders_to_unmount:
                    print(' '*4 + path)
                print('Unmounting them.')
                has_root = get_root()
            for path in folders_to_unmount:
                if not has_root:
                    break
                cmd = f'sudo umount {path}'
                exit_code, output = subprocess.getstatusoutput(cmd)
                if has_root and exit_code == 0:
                    folders_to_unmount.remove(path)
                    continue
                else:
                    print(output)

        if board_path:
            return board_path

        #  sample: '/dev/sdc1   CIRCUITPY'
        board_data = subprocess.getoutput(
            'lsblk -o PATH,LABEL | grep CIRCUITPY'
        )
        if board_data:
            board_path = board_data.strip().split(' ', 1)[0]
            os.system('mkdir -p CIRCUITPY')
            print('Mounting Raspberry PI Pico file system.')
            cmd = f'sudo mount {board_path} CIRCUITPY'
            has_root = get_root()
            if not has_root:
                print('Root access is needed to mount a file system.')
                print(f'You can mount it manually with "{cmd}"')
                return
            exit_code, output = subprocess.getstatusoutput(cmd)
            if exit_code != 0:
                print(output)
                return
            else:
                return get_board_path(retry=True)
        else:
            print('Raspberry PI Pico is not connected.')

def main():
    args = arg_parser.parse_args()
    print(get_board_path())
    #  print(vars(args))


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(
        description='Bind keyboard keys to Raspberry PI Pico\'s GPIO pins.'
    )
    arg_parser.add_argument(
        '-b',
        action=GetKeys,
        nargs=2,
        metavar=('PAD_BTN', 'KEY'),
        dest='bindings',
        help='Bind a pad button with a keyboard key.'
    )
    arg_parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List all bindings.'
    )
    arg_parser.add_argument(
        '-s', '--save',
        action='store_true',
        help='Save the bindings on disk.'
    )
    main()
