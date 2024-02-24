#!/usr/bin/env python
# file: setup.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2020 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2020-10-25T12:18:04+0100
# Last modified: 2024-02-24T22:13:12+0100
"""Install scripts for the local user."""

import ast
import hashlib
import os
import shutil
import sys
import sysconfig

# What to install
# The inner 2-tuples in setup.cfg consist of the name of the script and the
# extension it should have when installed on an ms-windows machine.
try:
    with open("setup.cfg") as cfg:
        setupline = cfg.read()
    SCRIPTS = ast.literal_eval(setupline)
    for a, b in SCRIPTS:
        if not isinstance(a, str) or len(a) == 0:
            raise ValueError("invalid script name")
        if not isinstance(b, str) or len(b) == 0:
            raise ValueError("invalid extension")
except Exception as e:
    print(f"ERROR: could not load configuration; “{e}”")
    sys.exit(1)


def main():
    cmd = None
    if len(sys.argv) == 2:
        cmd = sys.argv[1].lower()
    dirs = dirnames()
    if cmd not in ("install", "uninstall"):
        print(f"Usage {sys.argv[0]} [install|uninstall]")
        return 0
    # Actual (de)installation.
    for script, nt_ext in SCRIPTS:
        names = destnames(script, nt_ext, dirs)
        if cmd == "install":
            if not os.path.exists(dirs[0]):
                os.makedirs(dirs[0])
                print(f"Created “{dirs[0]}”. Do not forget to add it to your $PATH.")
            do_install(script, names)
        elif cmd == "uninstall":
            do_uninstall(script, names)
        else:
            print(f"* '{script}' would be installed as '{names[0]}'")
            if names[1]:
                print(f"  or '{names[1]}'")


def dirnames():
    if os.name == "posix":
        destdir = sysconfig.get_path("scripts", "posix_user")
        destdir2 = ""
    elif os.name == "nt":
        destdir = sysconfig.get_path("scripts", os.name)
        destdir2 = sysconfig.get_path("scripts", os.name + "_user")
    else:
        print(f"The system '{os.name}' is not recognized. Exiting")
        sys.exit(1)
    return destdir, destdir2


def destnames(script, nt_ext, dest):
    base = os.path.splitext(script)[0]
    if os.name == "posix":
        destname = dest[0] + os.sep + base
        destname2 = ""
    elif os.name == "nt":
        destname = dest[0] + os.sep + base + nt_ext
        destname2 = dest[1] + os.sep + base + nt_ext
    return destname, destname2


def should_install(source, destination):
    with open(source, "rb") as lf:
        srchash = hashlib.sha1(lf.read()).hexdigest()
    try:
        with open(destination, "rb") as lf:
            desthash = hashlib.sha1(lf.read()).hexdigest()
    except Exception:
        return True
    if srchash == desthash:
        return False
    return True


def do_install(script, dest):
    for d in dest:
        try:
            if should_install(script, d):
                shutil.copyfile(script, d)
                print(f"* installed '{script}' as '{d}'.")
                os.chmod(d, 0o700)
            else:
                print(f"* '{script}' and '{d}' are the same; not replaced.")
            break
        except (OSError, PermissionError, FileNotFoundError):
            pass  # Can't write to destination
    else:
        print(f"! installation of '{script}' has failed.")


def do_uninstall(script, dest):
    for d in dest:
        try:
            os.remove(d)
            print(f"* removed '{d}'")
        except FileNotFoundError:
            pass  # path doesn't exist


if __name__ == "__main__":
    main()
