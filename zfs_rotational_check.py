#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys

from typing import List

def is_rotational(block_device: str) -> bool:
    """
    Checks if given block device is "rotational" (spinning rust) or
    solid state block device.

    :param block_device: Path to block device to check

    :return: True if block device is a rotational block device,
             false otherwise
    """

    base_name = os.path.basename(block_device)
    rotational_file = f'/sys/block/{base_name}/queue/rotational'

    if not os.path.exists(rotational_file):
        # Maybe given path is not the base block device
        # -> Get disk for given block devices and try again
        disk = base_disk_for_block_device(block_device)
        if disk != block_device:
            return is_rotational(disk)

        raise Exception('Could not find file {}!'.format(rotational_file))

    with open(rotational_file, 'r') as f_obj:
        content = f_obj.read(1)
        if content == '1':
            return True
        if content == '0':
            return False

    raise Exception('Unknown value in {}!'.format(rotational_file))

def base_disk_for_block_device(partition: str) -> str:
    """
    Returns the base disk of a disk partition.

    :param partition: Path to the partition to get the base disk of

    :return: Path to base disk of given partition
    """

    # Follow link(s)
    # partition should now be in format '/dev/sda5'
    partition = os.path.realpath(partition)

    # Remove trailing number
    partition = re.sub('[0-9]+$', '', partition)

    return partition

def block_devices_for_pool(pool: str) -> List[str]:
    """
    Returns a list of all block devices for a given ZFS pool

    :param pool: The name of the pool the return all block devices of

    :return: List of paths to all block devices of given ZFS pool
    """

    if not isinstance(pool, str):
        raise Exception('Cannot get blockdevices for pool of type "{}"'.format(type(pool)))

    status_str = zpool_status(pool)
    if status_str is None:
        return []

    # Replaces tabs with spaces
    status_str = re.sub('\t+', ' ', status_str)

    # Squash multiple whitespaces
    status_str = re.sub(' +', ' ', status_str)

    # Strip whitespaces for every line
    status_str = '\n'.join(( line.strip() for line in status_str.split('\n') ))

    # Extract disk lines
    disk_re    = '(/dev/[a-zA-Z0-9/_-]*)'
    states_re  = '('
    states_re += '|'.join([ 'DEGRADED', 'FAULTED', 'OFFLINE', 'ONLINE', 'REMOVED', 'UNAVAIL' ])
    states_re += ')'
    num_re     = '([0-9][0-9]*)'
    line_re    = f'^{disk_re} {states_re} {num_re} {num_re} {num_re}$'

    reg = re.compile(line_re, re.MULTILINE)
    matches = reg.findall(status_str)

    devices = [ tup[0] for tup in matches ]
    return devices

def zpool_status(pool: str, timeout = -1) -> str:
    """
    Runs "zpool status" on a given pool and returns the output (stdout) string.

    :param pool: The pool name to run "zpool status" on

    :param timeout: Timeout until "zpool status" is assumend to have failed,
                   -1 for no timeout

    :return: The stdout output of the "zpool status" command for given pool
    """

    if not isinstance(pool, str):
        return None

    # Query zfs
    cmd_arr = ['zpool', 'status', '-P', pool]
    proc = subprocess.Popen(cmd_arr, stdout = subprocess.PIPE)
    stdout = None
    try:
        if timeout > 0:
            stdout, _ = proc.communicate(timeout = timeout)
        else:
            stdout, _ = proc.communicate()
    except subprocess.TimeoutExpired as error:
        proc.kill()
        txt = 'zpool status command did not return in time ({}s) for pool "{}"'
        raise Exception(txt.format(timeout, pool)) from error

    # Check return code
    if proc.returncode != 0:
        txt = 'zpool status command did not return successfully for pool "{}". Does pool exist?'
        raise Exception(txt.format(pool))

    # Encode output as UTF-8
    return stdout.decode('UTF-8')

def zpool_is_pure_solid_state(pool: str) -> bool:
    """
    Checks if a given ZFS pool only contains solid state devices.

    :param pool: The name of the pool to check

    :return: True if given ZFS pool only contains solid state devices,
             false otherwise
    """

    if not isinstance(pool, str):
        raise Exception('Cannot check pool of type "{}"'.format(type(pool)))

    # Get all block devices in pool
    disks = block_devices_for_pool(pool)

    # Get all disks in pool
    disks = [ base_disk_for_block_device(d) for d in disks ]
    disks = list(set(disks))

    rotationals = [ is_rotational(d) for d in disks ]

    # If at least one disk in pool is rotating rust
    # this pool is not a pure solid state pool
    return not True in rotationals

def main() -> int:
    """
    Main function.
    """

    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.description = '''
        Checks if a given pool consists only of non rotating drives.'''
    parser.add_argument(
        'pool',
        type = str,
        help = 'ZFS Pool to check. Given pool must already be imported.',
        metavar = 'POOL')
    args = parser.parse_args(sys.argv[1:])
    pool = args.pool

    # Check pool
    try:
        ssd_only = zpool_is_pure_solid_state(pool)
        print('Pool contains only SSD: {}'.format(ssd_only))
        return 0
    except BaseException as error:
        print(str(error), file = sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
