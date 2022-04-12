#!/usr/bin/env python3
# coding=utf-8
"""
Ppath Root Module
"""
import subprocess
import sys


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
