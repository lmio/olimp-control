#!/usr/bin/env python3

import hashlib
import os
import subprocess


def _get_dmi_string(name):
    try:
        return open(f"/sys/devices/virtual/dmi/id/{name}", "r").read().strip()
    except OSError:
        return ""


def get_machine_id():
    board_serial = _get_dmi_string("board_serial")
    chassis_serial = _get_dmi_string("chassis_serial")
    product_serial = _get_dmi_string("product_serial")

    concat = "".join((board_serial, chassis_serial, product_serial)).encode("utf-8")
    if not concat:
        # Probably a VM.
        concat = subprocess.check_output("cat /sys/class/net/*/address | sort", shell=True)

    return hashlib.sha1(concat).hexdigest()


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise PermissionError("Need root to read serial numbers")
    print(get_machine_id())
