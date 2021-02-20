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
__version__ = '0.1.0'
__all__ = [
  'Parser',
  'ParserOptions',
  'load_python_modules',
  'parse_python_module',
  'find_module',
  'iter_package_files',
  'DiscoveryResult',
  'discover'
]

from .parser import Parser, ParserOptions
from docspec import Argument, Module
from typing import Any, ContextManager, Iterable, List, Optional, TextIO, Tuple, Union
import contextlib
import io
import os
import nr.sumtype  # type: ignore
import sys


def load_python_modules(
  modules: List[str] = None,
  packages: List[str] = None,
  files: List[Tuple[Optional[str], Union[TextIO, str]]] = None,
  search_path: List[str] = None,
  options: ParserOptions = None,
  raise_: bool = True,
  encoding: Optional[str] = None,
) -> Iterable[Module]:
  """
  Utility function for loading multiple #Module#s from a list of Python module and package
  names. It combines #find_module(), #iter_package_files() and #parse_python_module() in a
  convenient way.

  :param modules: A list of module names to load and parse.
  :param packages: A list of package names to load and parse.
  :param files: A list of (module_name, filename) to parse. The filename may also be a
    file-like object. The module name may be None.
  :param search_path: The Python module search path. Falls back to #sys.path if omitted.
  :param options: Options for the Python module parser.
  :return: Iterable of #Module.
  """

  files = list(files) if files else []

  module_name: Optional[str]
  for module_name in modules or []:
    try:
      files.append((module_name, find_module(module_name, search_path)))
    except ImportError:
      if raise_:
        raise
  for package_name in packages or []:
    try:
      files.extend(iter_package_files(package_name, search_path))
    except ImportError:
      if raise_:
        raise

  for module_name, filename in files:
    yield parse_python_module(filename, module_name=module_name, options=options, encoding=encoding)


def parse_python_module(
    f: Union[str, TextIO],
    filename: str = None,
    module_name: str = None,
    options: ParserOptions = None,
    encoding: Optional[str] = None,
) -> Module:
  """
  Parses Python code of a file or file-like object and returns a #Module
  object with the contents of the file The *options* are forwarded to the
  #Parser constructor.
  """

  if isinstance(f, str):
    # TODO(NiklasRosenstein): If the file header contains a # coding: <name> comment, we should
    #   use that instead of the specified or system default encoding.
    with io.open(f, encoding=encoding) as fp:
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

  # NOTE(NiklasRosenstein): We cannot use #pkgutil.find_loader(), #importlib.find_lodaer()
  #   or #importlib.util.find_spec() as they weill prefer returning the module that is already
  #   loaded in #sys.module even if that instance would not be in the specified search_path.

  if search_path is None:
    search_path = sys.path

  filenames = [
    os.path.join(os.path.join(*module_name.split('.')), '__init__.py'),
    os.path.join(*module_name.split('.')) + '.py',
  ]

  for path in search_path:
    for choice in filenames:
      abs_path = os.path.normpath(os.path.join(path, choice))
      if os.path.isfile(abs_path):
        return abs_path

  raise ImportError(module_name)


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
    elif os.path.isdir(path):
      yield next(_recursive(module_name, os.path.join(path, '__init__.py')))
      for item in os.listdir(path):
        if item == '__init__.py':
          continue
        item_abs = os.path.join(path, item)
        name = module_name + '.' + item
        if name.endswith('.py'):
          name = name[:-3]
        if os.path.isdir(item_abs) and os.path.isfile(os.path.join(item_abs, '__init__.py')):
          for x in _recursive(name, item_abs):
            yield x
        elif os.path.isfile(item_abs) and item_abs.endswith('.py'):
          yield next(_recursive(name, item_abs))
    else:
      raise RuntimeError('path "{}" does not exist'.format(path))

  path = find_module(package_name, search_path)
  if os.path.basename(path).startswith('__init__.'):
    path = os.path.dirname(path)

    yield from _recursive(package_name, path)


@nr.sumtype.add_constructor_tests
class DiscoveryResult(nr.sumtype.Sumtype):
  Module = nr.sumtype.Constructor('name,filename')
  Package = nr.sumtype.Constructor('name,directory')


def discover(directory: str) -> Iterable[DiscoveryResult]:
  """
  Discovers Python modules and packages in the specified *directory*. The returned generated
  returns tuples where the first element of the tuple is the type (either `'module'` or
  `'package'`), the second is the name and the third is the path. In case of a package,
  the path points to the directory.

  :raises OSError: Propagated from #os.listdir().
  """

  # TODO (@NiklasRosenstein): Introspect the contents of __init__.py files to determine
  #   if we're looking at a namespace package. If we do, continue recursively.

  for name in os.listdir(directory):
    if name.endswith('.py'):
      yield DiscoveryResult.Module(name[:-3], os.path.join(directory, name))
    else:
      full_path = os.path.join(directory, name, '__init__.py')
      if os.path.isfile(full_path):
        yield DiscoveryResult.Package(name, os.path.join(directory, name))


def format_arglist(args: List[Argument]) -> str:
  """
  Formats a Python argument list.
  """

  result = []

  for arg in args:
    parts = []
    if arg.type == Argument.Type.KeywordOnly and '*' not in result:
      result.append('*')
    parts = [arg.name]
    if arg.datatype:
      parts.append(': ' + arg.datatype)
    if arg.default_value:
      if arg.datatype:
        parts.append(' ')
      parts.append('=')
    if arg.default_value:
      if arg.datatype:
        parts.append(' ')
      parts.append(arg.default_value)
    if arg.type == Argument.Type.PositionalRemainder:
      parts.insert(0, '*')
    elif arg.type == Argument.Type.KeywordRemainder:
      parts.insert(0, '**')
    result.append(''.join(parts))

  return ', '.join(result)
