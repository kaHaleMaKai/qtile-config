import os
import re
from setuptools import setup, find_packages  # type: ignore
import subprocess as sub
from pathlib import Path


dir = Path(__file__).parent
req_file = dir / "dev-requirements.txt"
anti_pattern = re.compile(r"^\s*#")
readme = dir / "README.md"
with readme.open("r") as f:
    long_desc = f.read()

tests = tuple(p.name for p in dir.glob("*test*"))

# do not attemp to change the set the version manually
# it will be filled in by the gitlab CI when pushing tags
version = os.environ.get("CI_COMMIT_TAG", "dev")

kwargs = dict(
    name="qtile-config",
    # do not attemp to change the set the version manually
    # it will be filled in by the gitlab CI when pushing tags
    version=version,
    description="Qtile Config – custom config for a hackable window manager",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url="https://github.com/kahamemakai/qtile-config",
    author="Lars Winderling",
    author_email="lars.winderling@posteo.de",
    license="private",
    package_dir={"qtile_config": "."},
    packages=find_packages(exclude=tests),
    package_data={".": ["py.typed"]},
    install_requires=[],
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Private",
        "Operating System :: Linux",
    ],
    python_requires=">=3.9",
)

if req_file.exists():
    dev_requirements = [dep for dep in req_file.read_text().split("\n") if dep and not anti_pattern.match(dep)]
    kwargs["extras_require"] = {"dev": dev_requirements}

setup(**kwargs)
