# coding=utf-8
"""
Setuid Module

`sudo cp python3 python`
`sudo chown root python`
`sudo chmod u+s,+x python`

sitecustomize.py
import os
os.seteuid(os.getuid())

site.py
after all imports:
os.seteuid(os.getuid())
HOME USER me da el usuario que ha entrado, pero si cambio entonces...
no cambia
"""

# TODO: aqui lo dejo. hacer el instalador. y luego el context manager según access o porque si
import os

from pathlib import Path
from string import Template

from subprocess import getoutput
from subprocess import run

from icecream import ic

template = Template("""#!/usr/bin/env python3
from pathlib import Path
${filename} = Path("/tmp/${filename}")
${filename}.touch()
print(${filename}.owner())
""")
tmp = Path('/tmp/setuid')

# tmp.mkdir(exist_ok=True)


def module():
    name = ic(module.__name__)
    file = tmp / f"{name}.py"

    file.write_text(template.substitute(filename=name))

    os.environ["PYTHONPATH"] = str(tmp)
    ic(getoutput(f"python3 -m {name}"))

    run(["sudo", "chown", "501:20", file])
    ic(getoutput(f"python3 -m {name}"))

    run(["sudo", "chmod", "+x", file])
    ic(getoutput(f"python3 -m {name}"))
    ic(getoutput(f"{file}"))


def path():
    name = ic(path.__name__)

    file = tmp / name
    file.touch()
    ic(file.owner())
    file.unlink()

    file.mkdir(exist_ok=True)
    ic(file.owner())
    run(["sudo", "rm", "-rf", file])


def profile():
    ic(profile.__name__)
    file = Path("/etc/profile")
    if os.access(file, os.W_OK, effective_ids=True):
        with file.open(mode='a') as fd:
            fd.write("")
        ic(f"{file}: updated")
    else:
        ic(f"{file}: no write access")


def spython():
    name = ic(spython.__name__)

    d = dict(filename="pipe")
    ic(getoutput(f"echo '{template.substitute(d)}' | python3"))

    d = dict(filename="heredoc")
    ic(getoutput(f"python3 <<<'{template.substitute(d)}'"))

    d = dict(filename="script")
    ic(getoutput(f"python3 -c '{template.substitute(d)}'"))

    ic(getoutput(f"python3 -c 'import os; print(os.getuid()); print(os.geteuid())'"))


def main():
    ic(os.getuid(), os.getgid(), os.geteuid(), os.getegid())
    # module()
    path()
    profile()


ic(os.environ["USER"])
ic(os.getuid(), os.getgid(), os.geteuid(), os.getegid())
print()

spython()
print()

main()
print()

ic(os.seteuid(1000))
main()
print()

ic(os.seteuid(0))
main()
print()

ic(os.seteuid(1000))
main()
print()

ic(os.seteuid(0))
main()

