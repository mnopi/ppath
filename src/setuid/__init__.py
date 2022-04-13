# coding=utf-8
"""
Setuid Package
"""
import sys
from pathlib import Path
from subprocess import getoutput


def main(*args):
    """
    Main function
    """
    if args and args[0] == 'demo':
        demo = Path(__file__).with_name('demo.py')
        getoutput(str(demo))

    print(args)
    pass


if __name__ == "__main__":
    main(*sys.argv[1:])

