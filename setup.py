#!/usr/bin/env python

# Setup script for the `pyjab' package.
#
# Author: Peter Odding <gaozhao89@qq.com>
# Last Change: May 27, 2021
# URL: https://github.com/gaozhao1989/pyjab

"""
Setup script for the `pyjab` package.

**python setup.py install**
  Install from the working directory into the current Python environment.

**python setup.py sdist**
  Build a source distribution archive.

**python setup.py bdist_wheel**
  Build a wheel distribution archive.
"""

# Standard library modules.
import codecs
import distutils.sysconfig
import os
import re
import sys

# De-facto standard solution for Python packaging.
from setuptools import find_packages, setup


def get_contents(*args):
    """Get the contents of a file relative to the source distribution directory."""
    with codecs.open(get_absolute_path(*args), "r", "UTF-8") as handle:
        return handle.read()


def get_version(*args):
    """Extract the version number from a Python module."""
    contents = get_contents(*args)
    metadata = dict(re.findall("__([a-z]+)__ = ['\"]([^'\"]+)", contents))
    return metadata["version"]


def get_requirements(*args):
    """Get requirements from pip requirement files."""
    requirements = set()
    with open(get_absolute_path(*args)) as handle:
        for line in handle:
            # Strip comments.
            line = re.sub(r"^#.*|\s#.*", "", line)
            # Ignore empty lines
            if line and not line.isspace():
                requirements.add(re.sub(r"\s+", "", line))
    return sorted(requirements)


def get_absolute_path(*args):
    """Transform relative pathnames into absolute pathnames."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)


def find_pth_directory():
    """
    Determine the correct directory pathname for installing ``*.pth`` files.

    To install a ``*.pth`` file using a source distribution archive (created
    when ``python setup.py sdist`` is called) the relative directory pathname
    ``lib/pythonX.Y/site-packages`` needs to be passed to the ``data_files``
    option to ``setup()``.

    Unfortunately this breaks universal wheel archives (created when ``python
    setup.py bdist_wheel --universal`` is called) because a specific Python
    version is now encoded in the pathname of a directory that becomes part of
    the supposedly universal archive :-).

    Through trial and error I've found that by passing the directory pathname
    ``/`` when ``python setup.py bdist_wheel`` is called we can ensure that
    ``*.pth`` files are installed in the ``lib/pythonX.Y/site-packages``
    directory without hard coding its location.
    """
    return (
        "/"
        if "bdist_wheel" in sys.argv
        else os.path.relpath(distutils.sysconfig.get_python_lib(), sys.prefix)
    )


setup(
    name="pyjab",
    version=get_version("pyjab", "__init__.py"),
    description="Python implementation for Java application UI automation with Java Access Bridge",
    long_description=get_contents("README.rst"),
    url="https://github.com/gaozhao1989/pyjab",
    author="Gary Gao",
    author_email="gaozhao89@qq.com",
    license="GPLv2",
    packages=find_packages(),
    install_requires=get_requirements("requirements.txt"),
    python_requires=">=3.8",
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Development Status :: 5 - Production/Stable",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Software Development :: Libraries :: Java Libraries",
        "Topic :: Home Automation",
        "Topic :: Utilities",
    ],
)
