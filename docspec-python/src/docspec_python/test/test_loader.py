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

"""
Tests the loading mechanism. Expects that the `docspec` and `docspec_python` modules
are installed. For a full test, they need to be installed as usual (not in develop
mode).
"""

from typing import List
import docspec
import docspec_python
import os
import pytest
import site


def _assert_modules_loaded(modules: List[docspec.Module]):
  assert modules[0].name == 'docspec_python'
  assert any(x.name == 'docspec_python.parser' for x in modules)


def test_discovery_from_sys_path():
  modules = list(docspec_python.load_python_modules(packages=['docspec_python']))
  _assert_modules_loaded(modules)


def test_discovery_search_path_overrides():
  modules = list(docspec_python.load_python_modules(
    packages=['docspec_python'], search_path=[], raise_=False))
  assert not modules


@pytest.mark.skipif(
  os.getenv('TEST_NO_DEVELOP') != 'true',
  reason='TEST_NO_DEVELOP needs to be set to "true" to test this case')
def test_discovery_search_path_overrides_docspec_python_in_install_mode():
  src_dir = os.path.normpath(__file__ + '/../../..')
  src_modules = list(docspec_python.load_python_modules(
    packages=['docspec_python'], search_path=[src_dir]))
  _assert_modules_loaded(src_modules)

  site_modules = list(docspec_python.load_python_modules(
    packages=['docspec_python'], search_path=site.getsitepackages()))
  _assert_modules_loaded(site_modules)

  assert site_modules[0].location.filename != src_modules[0].location.filename
