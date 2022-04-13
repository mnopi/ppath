#!/usr/bin/env spython
# coding=utf-8
"""
Setuid Module

`sudo cp python3 spython`
`sudo chown root spython`
`sudo chmod u+s,+x spython`
"""
import os

from pathlib import Path
from string import Template
from subprocess import getoutput
from subprocess import run

from mproject import EnvBuilder

template = Template("""#!/usr/bin/env spython
from pathlib import Path
${filename} = Path("/tmp/${filename}")
${filename}.touch()
print(${filename}.owner())
""")
tmp = Path('/tmp/setuid')
tmp.mkdir(exist_ok=True)


def create():
    name = create.__name__
    print(name)

    file = tmp / name

    EnvBuilder(env_dir=file)
    print(file.owner())
    run(["sudo", "rm", "-rf", file])


def module():
    name = module.__name__
    print(name)
    file = tmp / f"{name}.py"

    file.write_text(template.substitute(filename=name))

    os.environ["PYTHONPATH"] = str(tmp)
    print(getoutput(f"spython -m {name}"))

    run(["sudo", "chown", "501:20", file])
    print(getoutput(f"spython -m {name}"))

    run(["sudo", "chmod", "+x", file])
    print(getoutput(f"spython -m {name}"))
    print(getoutput(f"{file}"))


def path():
    name = path.__name__
    print(name)
    file = tmp / name
    file.touch()
    print(file.owner())
    file.unlink()

    file.mkdir(exist_ok=True)
    print(file.owner())
    run(["sudo", "rm", "-rf", file])


def profile():
    print(profile.__name__)
    file = Path("/etc/profile")
    if os.access(file, os.W_OK, effective_ids=True):
        with file.open(mode='a') as fd:
            fd.write("")
        print(f"{file}: updated")
    else:
        print(f"{file}: no write access")


def spython():
    name = spython.__name__
    print(name)

    d = dict(filename="pipe")
    print(getoutput(f"echo '{template.substitute(d)}' | spython"))

    d = dict(filename="heredoc")
    print(getoutput(f"spython <<<'{template.substitute(d)}'"))

    d = dict(filename="script")
    print(getoutput(f"spython -c '{template.substitute(d)}'"))

    print(getoutput(f"spython -c 'import os; print(os.getuid()); print(os.geteuid())'"))


def main():
    print(os.getuid(), os.geteuid())
    module()
    path()
    profile()
    create()


print(os.environ["USER"])


spython()

main()

os.setreuid(501, 0)
main()

os.setuid(0)
os.seteuid(501)
os.setreuid(0, 501)
main()

os.setuid(501)
os.seteuid(501)
main()

os.setuid(501)
os.setreuid(501, 501)
main()
