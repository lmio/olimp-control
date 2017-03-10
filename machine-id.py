#!/usr/bin/env python3

import hashlib
import subprocess

all_macs = subprocess.check_output("cat /sys/class/net/*/address | sort", shell=True)
print(hashlib.sha1(all_macs).hexdigest())
