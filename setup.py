#!/usr/bin/env python
# file: setup-user.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2020 R.F. Smith <rsmith@xs4all.nl>
# Created: 2020-10-25T12:18:04+0100
# Last modified: 2020-10-25T16:53:04+0100
"""Script to install scripts for the local user."""

import os
import shutil
import sys
import sysconfig

# What to install
scripts = ["gmsh-inp-filter"]

# Preparation
scheme = os.name + "_user"
destdir = sysconfig.get_path("scripts", scheme)
extensions = (".pyw", ".pyz", ".py")  # Don't change the order!
install = "install" in [a.lower() for a in sys.argv]
if os.name not in ("nt", "posix"):
    print(f"The system '{os.name}' is not recognized. Exiting")
    sys.exit(1)
if install:
    if not os.path.exists(destdir):
        os.mkdir(destdir)
else:
    print("(Use the 'install' argument to actually install scripts.)")
# Actual installation.
for script in scripts:
    for ext in extensions:
        src = script + ext
        if os.path.exists(src):
            if os.name == "nt":
                destname = destdir + os.sep + src
            elif os.name == "posix":
                destname = destdir + os.sep + script
            if install:
                shutil.copyfile(src, destname)
                os.chmod(destname, 0o700)
                print(f"* installed '{src}' as '{destname}'.")
            else:
                print(f"* '{src}' would be installed as '{destname}'")
            # Only the first extension found will be installed.
            continue
