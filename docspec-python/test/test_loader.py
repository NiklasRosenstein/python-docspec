# -*- coding: utf8 -*-
# Copyright (c) 2020 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

"""Tests the docspec loading mechanism. Expects that the `docspec` and `docspec_python` modules are installed.
For a full test, they need to be installed as usual (not in develop mode).
"""

import os
import typing as t
from pathlib import Path

import docspec
import pytest

import docspec_python


def _assert_is_docspec_python_module(modules: t.List[docspec.Module]) -> None:
    assert sorted(m.name for m in modules) == ["docspec_python", "docspec_python.__main__", "docspec_python.parser"]


def test_discovery_from_sys_path() -> None:
    """Tests that the `docspec_python` module can be loaded from `sys.path`."""

    modules = list(docspec_python.load_python_modules(packages=["docspec_python"]))
    _assert_is_docspec_python_module(modules)


def test_discovery_search_path_overrides() -> None:
    """Tests that the `docspec_python` module will not be loaded if an empty search path is supplied."""

    modules = list(docspec_python.load_python_modules(packages=["docspec_python"], search_path=[], raise_=False))
    assert not modules


@pytest.mark.skipif(
    os.getenv("DOCSPEC_TEST_NO_DEVELOP") != "true",
    reason='DOCSPEC_TEST_NO_DEVELOP needs to be set to "true" to test this case',
)
def test_discovery_search_path_overrides_docspec_python_in_install_mode() -> None:
    """Tests that the `docspec_python` module can be loaded separately from the local project source code as well
    as from the system site-packages independently by supplying the right search path."""

    src_dir = os.path.normpath(__file__ + "/../../src")
    src_modules = list(docspec_python.load_python_modules(packages=["docspec_python"], search_path=[src_dir]))
    _assert_is_docspec_python_module(src_modules)

    # NOTE: Since we moved to UV, it seems to be adding the local project source code to the sys.path, so we
    #       don't actually import docspec from site-packages. This test is disabled for now.

    # site_modules = list(
    #     docspec_python.load_python_modules(packages=["docspec_python"], search_path=site.getsitepackages())
    # )
    # _assert_is_docspec_python_module(site_modules)

    # assert site_modules[0].location.filename != src_modules[0].location.filename


def test_pep420_namespace_package() -> None:
    """Tests that PEP 420 namespace packages can be loaded."""

    src_dir = Path(__file__).parent / "src"

    # Test that the module can be loaded explicitly.
    src_modules = list(
        docspec_python.load_python_modules(modules=["pep420_namespace_package.module"], search_path=[src_dir])
    )

    assert len(src_modules) == 1
    assert src_modules[0].name == "pep420_namespace_package.module"

    # Test that the module can be loaded implicitly.
    src_modules = list(docspec_python.load_python_modules(packages=["pep420_namespace_package"], search_path=[src_dir]))

    assert len(src_modules) == 1
    assert src_modules[0].name == "pep420_namespace_package.module"
