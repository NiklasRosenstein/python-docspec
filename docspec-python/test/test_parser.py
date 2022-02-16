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

from docspec import *
from docspec_python import parse_python_module, ParserOptions
from functools import wraps
from io import StringIO
from json import dumps
from textwrap import dedent
from typing import List, Optional
import pytest
import sys


def unset_location(obj: ApiObject):
  obj.location = None
  #if obj.docstring:
  #  obj.docstring = Docstring(obj.docstring.content, None)
  if isinstance(obj, HasMembers):
    for member in obj.members:
      unset_location(member)


def docspec_test(module_name=None, parser_options=None, strip_locations: bool = True):
  """
  Decorator for docspec unit tests.
  """

  def decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
      parsed_module = parse_python_module(
        StringIO(dedent(func.__doc__)),
        module_name=module_name or func.__name__.lstrip('test_'),
        options=parser_options,
        filename=func.__name__,
      )
      parsed_module.location = None
      if strip_locations:
        unset_location(parsed_module)
      reference_module = Module(name=parsed_module.name, location=None, docstring=None, members=func(*args, **kwargs))
      assert dumps(dump_module(reference_module), indent=2) == dumps(dump_module(parsed_module), indent=2)
    return wrapper
  return decorator


@docspec_test()
def test_funcdef_1():
  """
  def a():
    ' A simple function. '
  """

  return [
    Function(
      name='a',
      location=None,
      docstring=Docstring('A simple function.', Location('test_funcdef_1', 2)),
      modifiers=None,
      args=[],
      return_type=None,
      decorations=[])
  ]


@docspec_test()
def test_funcdef_2():
  """
  def b(a: int, *, c: str, **opts: Any) -> None:
    ' This uses annotations and keyword-only arguments. '
  """

  return [
    Function(
      name='b',
      location=None,
      docstring=Docstring('This uses annotations and keyword-only arguments.', Location('test_funcdef_2', 2)),
      modifiers=None,
      args=[
        Argument('a', Argument.Type.POSITIONAL, None, 'int', None),
        Argument('c', Argument.Type.KEYWORD_ONLY, None, 'str', None),
        Argument('opts', Argument.Type.KEYWORD_REMAINDER, None, 'Any', None),
      ],
      return_type='None',
      decorations=[],
    )
  ]


@docspec_test()
def test_funcdef_3():
  """
  @classmethod
  @db_session(sql_debug=True)
  def c(self, a: int, b, *args, opt: str) -> Optional[int]:
    ' More arg variations. '
  """

  return [
    Function(
      name='c',
      location=None,
      docstring=Docstring('More arg variations.', Location('test_funcdef_3', 4)),
      modifiers=None,
      args=[
        Argument('self', Argument.Type.POSITIONAL, None, None, None),
        Argument('a', Argument.Type.POSITIONAL, None, 'int', None),
        Argument('b', Argument.Type.POSITIONAL, None, None, None),
        Argument('args', Argument.Type.POSITIONAL_REMAINDER, None, None, None),
        Argument('opt', Argument.Type.KEYWORD_ONLY, None, 'str', None),
      ],
      return_type='Optional[int]',
      decorations=[
        Decoration('classmethod', None),
        Decoration('db_session', '(sql_debug=True)'),
      ],
    )
  ]


@docspec_test()
def test_funcdef_4():
  """
  def fun(project_name, project_type, port=8001):
    pass
  """

  return [
    Function(
      name='fun',
      location=None,
      docstring=None,
      modifiers=None,
      args=[
        Argument('project_name', Argument.Type.POSITIONAL, None, None, None),
        Argument('project_type', Argument.Type.POSITIONAL, None, None, None),
        Argument('port', Argument.Type.POSITIONAL, None, None, '8001'),
      ],
      return_type=None,
      decorations=[],
    )
  ]


@docspec_test(parser_options=ParserOptions(treat_singleline_comment_blocks_as_docstrings=True))
def test_funcdef_5_single_stmt():
  """
  def func1(self): return self.foo

  def func2(self):
    # ABC
    #   DEF
    return self.foo

  def func3(self):
    ''' ABC
      DEF '''
    return self.foo

  def func4(self):
    '''
    ABC
      DEF
    '''
    return self.foo
  """

  def mkfunc(name: str, docstring: Optional[str], lineno: int) -> Function:
    return Function(
      name=name,
      location=None,
      docstring=Docstring(docstring, Location('test_funcdef_5_single_stmt', lineno)) if docstring else None,
      modifiers=None,
      args=[Argument('self', Argument.Type.POSITIONAL, None, None, None)],
      return_type=None,
      decorations=[],
    )

  return [
    mkfunc('func1', None, 1),
    mkfunc('func2', 'ABC\nDEF', 4),
    mkfunc('func3', 'ABC\nDEF', 9),
    mkfunc('func4', 'ABC\n  DEF', 14),
  ]


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6 or higher")
@docspec_test()
def test_funcdef_6_starred_args():
  """
  def func1(a, *, b, **c): pass

  def func2(*args, **kwargs):
    ''' Docstring goes here. '''

  def func3(*, **kwargs):
    ''' Docstring goes here. '''

  def func4(abc, *,):
    '''Docstring goes here'''

  def func5(abc, *, kwonly):
    '''Docstring goes here'''
  """

  def mkfunc(name: str, docstring: Optional[str], lineno: int, args: List[Argument]) -> Function:
    return Function(
      name=name,
      location=None,
      docstring=Docstring(docstring, Location('test_funcdef_6_starred_args', lineno)) if docstring else None,
      modifiers=None,
      args=args,
      return_type=None,
      decorations=[],
    )

  return [
    mkfunc('func1', None, 0, [
      Argument('a', Argument.Type.POSITIONAL, None, None, None),
      Argument('b', Argument.Type.KEYWORD_ONLY, None, None, None),
      Argument('c', Argument.Type.KEYWORD_REMAINDER, None, None, None),
    ]),
    mkfunc('func2', 'Docstring goes here.', 4, [
      Argument('args', Argument.Type.POSITIONAL_REMAINDER, None, None, None),
      Argument('kwargs', Argument.Type.KEYWORD_REMAINDER, None, None, None),
    ]),
    mkfunc('func3', 'Docstring goes here.', 7, [
      Argument('kwargs', Argument.Type.KEYWORD_REMAINDER, None, None, None),
    ]),
    mkfunc('func4', 'Docstring goes here', 10, [
      Argument('abc', Argument.Type.POSITIONAL, None, None, None),
    ]),
    mkfunc('func5', 'Docstring goes here', 13, [
      Argument('abc', Argument.Type.POSITIONAL, None, None, None),
      Argument('kwonly', Argument.Type.KEYWORD_ONLY, None, None, None),
    ]),
  ]


@docspec_test()
def test_classdef_1_exceptions():
  """
  class MyError1:
    pass

  class MyError2():
    pass

  class MyError3(RuntimeError):
    pass

  class MyError4(RuntimeError, object, metaclass=ABCMeta):
    pass

  class MyError5(metaclass=ABCMeta):
    pass

  class MyError6(RuntimeError):
    __metaclass__ = ABCMeta
  """

  return [
    Class(
      name='MyError1',
      location=None,
      docstring=None,
      metaclass=None,
      bases=[],
      decorations=None,
      members=[]
    ),
    Class(
      name='MyError2',
      location=None,
      docstring=None,
      metaclass=None,
      bases=[],
      decorations=None,
      members=[]
    ),
    Class(
      name='MyError3',
      location=None,
      docstring=None,
      metaclass=None,
      bases=['RuntimeError'],
      decorations=None,
      members=[]
    ),
    Class(
      name='MyError4',
      location=None,
      docstring=None,
      metaclass='ABCMeta',
      bases=['RuntimeError', 'object'],
      decorations=None,
      members=[]
    ),
    Class(
      name='MyError5',
      location=None,
      docstring=None,
      metaclass='ABCMeta',
      bases=[],
      decorations=None,
      members=[]
    ),
    Class(
      name='MyError6',
      location=None,
      docstring=None,
      metaclass='ABCMeta',
      bases=['RuntimeError'],
      decorations=None,
      members=[]
    ),
  ]


@docspec_test(strip_locations=False)
def test_indirections():
  """
  import os
  import urllib.request as r
  import os.path, \
    sys, pathlib as P
  from sys import platform, executable as EXE
  from os.path import *
  from pathlib import (
    PurePath as PP,
    PosixPath
  )
  from .. import core
  from ..core import Widget, View
  from .vendor import pkg_resources, six
  from ...api import *
  def foo():
    from sys import platform
  class bar:
    import os
    from os.path import dirname
  """

  return [
    Indirection('os', Location('test_indirections', 2), None, 'os'),
    Indirection('r', Location('test_indirections', 3), None, 'urllib.request'),
    Indirection('path', Location('test_indirections', 4), None, 'os.path'),
    Indirection('sys', Location('test_indirections', 4), None, 'sys'),
    Indirection('P', Location('test_indirections', 4), None, 'pathlib'),
    Indirection('platform', Location('test_indirections', 5), None, 'sys.platform'),
    Indirection('EXE', Location('test_indirections', 5), None, 'sys.executable'),
    Indirection('*', Location('test_indirections', 6), None, 'os.path.*'),
    Indirection('PP', Location('test_indirections', 8), None, 'pathlib.PurePath'),
    Indirection('PosixPath', Location('test_indirections', 9), None, 'pathlib.PosixPath'),
    Indirection('core', Location('test_indirections', 11), None, '..core'),
    Indirection('Widget', Location('test_indirections', 12), None, '..core.Widget'),
    Indirection('View', Location('test_indirections', 12), None, '..core.View'),
    Indirection('pkg_resources', Location('test_indirections', 13), None, '.vendor.pkg_resources'),
    Indirection('six', Location('test_indirections', 13), None, '.vendor.six'),
    Indirection('*', Location('test_indirections', 14), None, '...api.*'),
    Function('foo', Location('test_indirections', 15), None, None, [], None, []),
    Class('bar', Location('test_indirections', 17), None, None, [], None, [
      Indirection('os', Location('test_indirections', 18), None, 'os'),
      Indirection('dirname', Location('test_indirections', 19), None, 'os.path.dirname'),
    ])
  ]
