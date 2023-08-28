"""
File: main.py
Author: Chuncheng Zhang
Date: 2023-08-28
Copyright & Email: chuncheng.zhang@ia.ac.cn

Purpose:
    Amazing things

Functions:
    1. Requirements and constants
    2. Function and class
    3. Play ground
    4. Pending
    5. Pending
"""


# %% ---- 2023-08-28 ------------------------
# Requirements and constants
import os
import re
import shlex
import argparse
import warnings
import platform
import subprocess

import pandas as pd

from pathlib import Path
from rich import print, inspect


# %% ---- 2023-08-28 ------------------------
# Function and class
def content2blocks(content, block_divider='\n\n', ignore_empty_block_flag=True):
    """Parse the content of `lspci -vmm` into blocks

    Args:
        content (str): The raw output.
        block_divider (str, optional): The divider between the blocks. Defaults to '\n\n'.
        ignore_empty_block_flag (bool, optional): Whether ignore the empty block. Defaults to True.

    Returns:
        list: The list of the blocks, each array is a string.
    """
    if ignore_empty_block_flag:
        return [e for e in content.split(block_divider) if e.strip()]
    else:
        return content.split(block_divider)


def block2dict(block, row_divider='\n', name_divider=':\t'):
    """Convert the block into a dict

    Args:
        block (str): The string of one block.
        row_divider (str, optional): The divider between the rows. Defaults to '\n'.
        name_divider (str, optional): The divider between the name and its value. Defaults to ':\t'.

    Returns:
        dict: The dict of the rows.
    """
    output = dict()

    for row in block.split(row_divider):
        if not name_divider in row:
            warnings.warn(f"Invalid row: {row}", category=UserWarning)
            continue

        name, value = row.split(name_divider, 1)
        output[name] = value

    return output


def new_session(name='New session', length=80):
    """Start a new operating session of the CLI output

    Args:
        name (str, optional): The name of the session. Defaults to 'New session'.
        length (int, optional): The length of the '-' line. Defaults to 80.
    """
    print('\n')
    print('-' * length)
    print(f'---- [bold blue]{name}[/bold blue] ----')


def generate_template():
    """Generate the templates for xorg.conf

    Returns:
        tuple: (str, str, str):
            str: device_section.
            str: screen_section.
            str: server_layout_section.
    """

    device_section = """
Section "Device"
    Identifier     "Device{device_id}"
    Driver         "nvidia"
    VendorName     "NVIDIA Corporation"
    BusID          "{bus_id}"
    Screen         {_screen_id}
EndSection
"""

    screen_section = """
Section "Screen"
    Identifier     "Screen{screen_id}"
    Device         "Device{device_id}"
    DefaultDepth    24
    Option         "AllowEmptyInitialConfiguration" "True"
    SubSection     "Display"
        Depth       24
        Virtual 1024 768
    EndSubSection
EndSection
"""

    server_layout_section = """
Section "ServerLayout"
    Identifier     "Default Layout"
    {screen_records}
EndSection
"""

    return device_section, screen_section, server_layout_section


def generate_xorg_conf(devices: pd.DataFrame, n_screens=3):
    device_section, screen_section, server_layout_section = generate_template()

    xorg_conf = []
    screen_records = []

    # Append the device_conf and screen_conf one-by-one
    device_id = 0
    for idx_device in range(len(devices)):
        se = devices.iloc[idx_device]
        bus_id = se['BusID']

        for _screen_id in range(n_screens):
            print(
                f'PCI: {bus_id}, DeviceID: {device_id} (screen: {_screen_id}), screenID: {device_id}')
            # Bind the device_id with bus_id,
            # and assign the _screen_id to it
            xorg_conf.append(device_section.format(
                device_id=device_id, bus_id=bus_id, _screen_id=_screen_id))

            # The screen_id is named as the same as the device_id,
            # since it is unique
            xorg_conf.append(screen_section.format(
                device_id=device_id, screen_id=device_id))
            screen_records.append(
                'Screen {screen_id} "Screen{screen_id}" 0 0'.format(screen_id=device_id))

            # Each device_id is only used once
            device_id += 1

    # Append the server_layout_section at the end of the file
    xorg_conf.append(server_layout_section.format(
        screen_records="\n    ".join(screen_records)))

    output = '\n'.join(xorg_conf)
    return output


# %% ---- 2023-08-28 ------------------------
# Play ground
if __name__ == "__main__":
    # ----------------------------------------------------------
    parser = argparse.ArgumentParser(description='Xorg simulation')
    parser.add_argument(
        '-d', '--display', metavar='int', type=int, default=13,
        help='display port')

    args = parser.parse_args()

    # ----------------------------------------------------------
    assert platform.system() == 'Linux', 'Only Linux systems are supported'

    # ----------------------------------------------------------
    new_session('Command execution')
    command = shlex.split('lspci -mm -v')
    # Call the command script and wait for the output
    output = subprocess.check_output(command).decode()
    print(command)

    # ----------------------------------------------------------
    new_session('Parse output')
    blocks = content2blocks(output)
    dcts = [block2dict(e) for e in blocks]
    raw_table = pd.DataFrame(dcts)
    print(raw_table)

    # ----------------------------------------------------------
    new_session('Group by Vender & Class')
    group = raw_table.groupby(['Vendor', 'Class'])
    # inspect(group)
    # print(group.groups)
    print(group.count())

    # ----------------------------------------------------------
    new_session('Device of interest (doi)')
    doi_table = group.get_group(('NVIDIA Corporation', '3D controller')).copy()
    print(doi_table)

    # ----------------------------------------------------------
    new_session('Append BusID')
    doi_table['BusID'] = doi_table['Slot'].map(
        lambda s: 'PCI:' + ':'.join(map(lambda x: str(int(x, 16)), re.split(r'[:\.]', s))))
    print(doi_table)

    # ----------------------------------------------------------
    new_session('Xorg simulation')
    try:
        command = generate_xorg_conf(doi_table)

        xorg_search_path = '/etc/X11'
        xorg_search_path = './'

        display = args.display
        print(f'Working with $DISPLAY=:{display}')
        relative_path = f'custom-xorg-conf/tmpfile-{display}.conf'
        path = Path(xorg_search_path, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            f.write(command)

        # The following command will startup the Xorg display
        # command = shlex.split("Xorg -noreset +extension GLX +extension RANDR +extension RENDER -config %s :%s" % (relative_path, display))
        # subprocess.call(command)

        input('Press enter to escape.')

    finally:
        # os.unlink(path)
        print(
            f'The file {path} was designed to be deleted by `os.unlink(path)`, but for example usage it is not executed.')


# %% ---- 2023-08-28 ------------------------
# Pending


# %% ---- 2023-08-28 ------------------------
# Pending
