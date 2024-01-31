import os
import re
import yaml
import hashlib
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from libqtile.log_utils import logger
from qutely.vars import get_config

cur_dir = Path(__file__).absolute().parent


def get_template(file):
    templates_dir = cur_dir / "templates"
    loader = FileSystemLoader(templates_dir)
    return Environment(loader=loader, line_comment_prefix="#j2:", enable_async=True).get_template(
        file
    )


async def render(
    src,
    dest,
    keep_empty=True,
    keep_comments=True,
    comment_start="#",
    keep_modelines=True,
    overrides=None,
) -> bool:
    dest = os.path.abspath(os.path.expanduser(dest))
    src = src if src.endswith(".j2") else f"{src}.j2"
    if os.path.isdir(dest):
        dest = os.path.join(dest, src.replace(".j2", ""))
    if os.path.exists(dest):
        with open(dest, "rb") as f:
            old_hash = hashlib.md5(f.read()).hexdigest()
    else:
        old_hash = None
    t = get_template(src)

    src_vars = get_config(src)

    _content = await t.render_async(**src_vars)
    if keep_comments and keep_empty:
        content = _content
    else:
        lines = []
        for line in _content.split("\n"):
            if not line.strip():
                if keep_empty:
                    lines.append(line)
                else:
                    continue
            elif re.match(r"^\s*{} vim:".format(comment_start), line):
                if keep_modelines:
                    lines.append(line)
                else:
                    continue
            elif re.match(r"^\s*{}".format(comment_start), line):
                if keep_comments:
                    lines.append(line)
                else:
                    continue
            else:
                lines.append(line)
        content = "\n".join(lines)

    new_hash = hashlib.md5(content.encode()).hexdigest()
    if not old_hash == new_hash:
        with open(dest, "w") as f:
            f.write(content)
        return True
    else:
        return False
