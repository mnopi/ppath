#!/usr/local/bin/sbash
# shellcheck shell=bash
PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")"):${PATH}"
export PATH

geteuid

touch /tmp/demo.sh.user
ls -la /tmp/demo.sh.user

seteuid 0
touch /tmp/demo.sh.root
ls -la /tmp/demo.sh.root
