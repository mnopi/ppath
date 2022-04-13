#!/usr/bin/env setid_python_test
# coding=utf-8
"""
Ppath Root Module
"""
import os
import subprocess
import sys

from pathlib import Path
# Works:
#  /Users/j5pu/ppath/src/setreuid_root.py
#  /Users/j5pu/ppath/src/setreuid_user.py
#  setid_python_test -m setreuid_root
#  setid_python_test -m setreuid_user
# Does not work:
#  /Users/j5pu/ppath/src/setreuid_root_python_normal.py
#  /Users/j5pu/ppath/src/env python3

# CONCLUSION: cambiar el interpreter y mirar si al crear el venv se jode. Hacer set del grupo tambien ??
# el ven lo crea todo con root, todo, todo,...
# O SEA: o lo dejo fijo en el python o con un context manager o algo asi, y llamar
# hacer un sitecustomize con esto !!!


print(os.access("/etc/profile", os.W_OK, effective_ids=True))
print(os.getuid())
print(os.geteuid())

profile = Path("/etc/profile")
with profile.open(mode='a') as fd:
    fd.write("echo hola\n")

temp = Path("/tmp/user")
temp.touch()
print(temp.owner())


def setreuid(ruid, euid, pid=None):
    """
    Set real and effective user ids.
    """
    import os
    import pwd
    import grp

    ruid = pwd.getpwnam(ruid).pw_uid
    euid = pwd.getpwnam(euid).pw_uid
    os.setreuid(ruid, euid)
    os.setregid(ruid, euid)
    os.setgroups([])
    os.setresgid(ruid, euid, ruid)
    os.setresuid(ruid, euid, ruid)
    subprocess.run(['-m', 'os', 'setuid', str(ruid)])
