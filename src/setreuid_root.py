#!/usr/bin/env setid_python_test
# coding=utf-8
"""
Ppath Root Module
"""
import os
import subprocess
import sys

from pathlib import Path

print(os.access("/etc/profile", os.W_OK, effective_ids=True))
print(os.getuid())
print(os.geteuid())

profile = Path("/etc/profile")
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
