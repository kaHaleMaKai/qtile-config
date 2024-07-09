#!/bin/bash
set -euo pipefail

cur_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]:-.}")")"

export PYTHONPATH=''
DEFAULT_VENV_ROOT="${HOME}/venvs"

qtile_dir="${HOME}/github/qtile/qtile"
qtile_extras_dir="${HOME}/github/elParaguayo/qtile-extras"

pip-install() {
  uv pip install -c "${cur_dir}/constraints.txt" "$@"
}

print_help() {
  cat <<'EOF'
Install qtile.

Options:
    --live                      modify the production environment instead of (default) testing
    --install                   install a venv including all requirements
    --uninstall                 uninstall the qtile venv
    --reinstall                 uninstall and then install a venv including all requirements
    --python=PYTHON,-p PYTHON   use the specified python interpreter for the venv
    --help,-h                   print this help text and exit
    --tag=TAG,-t TAG            install a specific git tag
    --extras-tag=TAG,-T TAG            install a specific git tag
    --venv-dir=DIR              path to virtual env to create
EOF
}

main() {
  local do_install=0
  local do_uninstall=0
  local test=1
  local _python=python3
  local tag extras_tag venv_dir qtile
  if ! (($#)); then
    echo '[ERROR] no arguments given. use "--help" to display a help message' >&2
    exit 1
  fi
  while (($#)); do
    case "$1" in
      --live) test=0
        ;;
      --install|install) do_install=1
        ;;
      --uninstall|uninstall) do_uninstall=1
        ;;
      --reinstall|reinstall)
        do_install=1
        do_uninstall=1
        ;;
      --python=*) _python="${1#*=}"
        ;;
      -p)
        _python="$2"
        shift
        ;;
      --tag=*) tag="${1#*=}"
        ;;
      -t)
        tag="$2"
        shift
        ;;
      --extras-tag=*) extras_tag="${1#*=}"
        ;;
      -T)
        extras_tag="$2"
        shift
        ;;
      --help|-h)
        print_help
        exit
        ;;
      --venv-dir=*) venv_dir="${1#*=}"
        ;;
      -V)
        venv_dir="$2"
        shift
        ;;
      *) echo "[ERROR] got unknown action '${1}'" >&2
         exit 12
     esac
     shift
   done

   if [[ -z "${tag}" ]]; then
     echo '[ERROR] missing tag argument' >&2
     exit 1
   fi

   local config_dir="${HOME}/.config"
   if (($test)); then
     qtile='qtile-test'
   else
     qtile='qtile'
   fi
   config_dir="${config_dir}/${qtile}"

  if [[ -z "${venv_dir:-}" ]]; then
    venv_dir="${HOME}/venvs/${qtile}"
  fi
  local venv_file="${config_dir}/activate-venv"

  if ((do_uninstall)); then
    rm -f "$venv_file"
    if [[ -d "$venv_dir" ]]; then
      echo "[INFO] removing ${venv_dir}" >&2
      rm -rf "${venv_dir}"
    fi
    echo '[INFO] not installed yet' >&2
  fi

  if !((do_install)); then
    exit
  fi
  echo '[INFO] please make sure to run `apt install python3-gi` as well' >&2

  if [[ -d "$venv_dir" ]]; then
    echo "[ERROR] dir '${venv_dir}' already exists" >&2
    exit 11
  fi
  uv venv --python="$_python" "$venv_dir"
  source "${venv_dir}/bin/activate"
  pip-install --upgrade wheel setuptools
  pip-install -r <(cat requirements.txt; echo "qtile==${tag}";)

  cd "$qtile_extras_dir"
  git checkout "${extras_tag:-${tag}}"
  pip-install .

  uv pip freeze > "${venv_dir}/requirements.txt"
  ln -s -T "${venv_dir}/bin/activate" "$venv_file"
}

main "$@"

# vim: ft=sh
