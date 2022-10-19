#!/bin/bash
set -euo pipefail
set -xv

# /etc/X11/xinit/xinitrc
#
# global xinitrc file, used by all X sessions started by xinit (startx)

# invoke global X session script

# export SCREEN_SIZE=1024x768
# export QTILE_DEBUG_MODE=on
export QTILE_CHECKCLOCK_DB=/tmp/checkclock.sqlite
config_dir="${HOME}/.config/qtile-test"
bin_dir="${HOME}/venvs/qtile-test/bin"
export LOG_LEVEL=DEBUG
# export QTILE_MOD_KEY=mod1
export PYTHONASYNCIODEBUG=1

"${bin_dir}/python" "${bin_dir}/qtile" start --config "${config_dir}/config.py"

# vim: ft=sh
