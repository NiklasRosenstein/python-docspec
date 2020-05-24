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

__author__ = 'Niklas Rosenstein <rosensteinniklas@gmail.com>'
__version__ = '0.0.3'
__all__ = ['parse_python_module', 'Parser', 'find_module', 'iter_package_files']

from .parser import Parser, ParserOptions
from docspec import Module
from typing import Any, Iterable, List, TextIO, Tuple, Union
import os
import pkgutil
import sys


def parse_python_module(
    f: Union[str, TextIO],
    filename: str = None,
    module_name: str = None,
    options: ParserOptions = None
) -> Module:
  """
  Parses Python code of a file or file-like object and returns a #Module
  object with the contents of the file The *options* are forwarded to the
  #Parser constructor.
  """

  if isinstance(f, str):
    with open(f) as fp:
      return parse_python_module(fp, filename, module_name, options)

  filename = filename or getattr(f, 'name', None)
  parser = Parser(options)
  ast = parser.parse_to_ast(f.read(), filename)
  return parser.parse(ast, filename, module_name)


def find_module(module_name: str, search_path: List[str] = None) -> str:
  """
  Finds the filename of a module that can be parsed with #parse_python_module().
  If *search_path* is not set, the default #sys.path is used to search for the
  module.

  :raise ImportError: If the module cannot be found.
  """

  old_path = sys.path
  if search_path is not None:
    sys.path = search_path

  try:
    loader = pkgutil.find_loader(module_name)
    if loader is None:
      raise ImportError(module_name)
    return loader.get_filename()
  finally:
    sys.path = old_path


def iter_package_files(
  package_name: str,
  search_path: List[str] = None,
) -> Iterable[Tuple[str, str]]:
  """
  Returns an iterator for the Python source files in the specified package. The items returned
  by the iterator are tuples of the module name and filename.
  """

  def _recursive(module_name, path):
    # pylint: disable=stop-iteration-return
    if os.path.isfile(path):
      yield module_name, path
      return
    elif os.path.isdir(path):
      yield next(_recursive(module_name, os.path.join(path, '__init__.py')))
      for item in os.listdir(path):
        if item == '__init__.py':
          continue
        item_abs = os.path.join(path, item)
        name = module_name + '.' + item.rstrip('.py')
        if os.path.isdir(item_abs) and os.path.isfile(os.path.join(item_abs, '__init__.py')):
          for x in _recursive(name, item_abs):
            yield x
        elif os.path.isfile(item_abs) and item_abs.endswith('.py'):
          yield next(_recursive(name, item_abs))
      return
    else:
      raise RuntimeError('path "{}" does not exist'.format(path))

  path = find_module(package_name)
  if os.path.basename(path).startswith('__init__.'):
    path = os.path.dirname(path)

  yield from _recursive(package_name, path)
