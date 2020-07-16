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


def unset_location(obj):
  obj.location = None
  for member in getattr(obj, 'members', []):
    unset_location(member)


def docspec_test(module_name=None, parser_options=None):
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
      docstring='A simple function.',
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
      docstring='This uses annotations and keyword-only arguments.',
      modifiers=None,
      args=[
        Argument('a', Argument.Type.Positional, None, 'int', None),
        Argument('c', Argument.Type.KeywordOnly, None, 'str', None),
        Argument('opts', Argument.Type.KeywordRemainder, None, 'Any', None),
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
      docstring='More arg variations.',
      modifiers=None,
      args=[
        Argument('self', Argument.Type.Positional, None, None, None),
        Argument('a', Argument.Type.Positional, None, 'int', None),
        Argument('b', Argument.Type.Positional, None, None, None),
        Argument('args', Argument.Type.PositionalRemainder, None, None, None),
        Argument('opt', Argument.Type.KeywordOnly, None, 'str', None),
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
        Argument('project_name', Argument.Type.Positional, None, None, None),
        Argument('project_type', Argument.Type.Positional, None, None, None),
        Argument('port', Argument.Type.Positional, None, None, '8001'),
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

  def mkfunc(name: str, docstring: Optional[str]) -> Function:
    return Function(
      name=name,
      location=None,
      docstring=docstring,
      modifiers=None,
      args=[Argument('self', Argument.Type.Positional, None, None, None)],
      return_type=None,
      decorations=[],
    )

  return [
    mkfunc('func1', None),
    mkfunc('func2', 'ABC\nDEF'),
    mkfunc('func3', 'ABC\nDEF'),
    mkfunc('func4', 'ABC\n  DEF'),
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

  def mkfunc(name: str, docstring: Optional[str], args: List[Argument]) -> Function:
    return Function(
      name=name,
      location=None,
      docstring=docstring,
      modifiers=None,
      args=args,
      return_type=None,
      decorations=[],
    )

  return [
    mkfunc('func1', None, [
      Argument('a', Argument.Type.Positional, None, None, None),
      Argument('b', Argument.Type.KeywordOnly, None, None, None),
      Argument('c', Argument.Type.KeywordRemainder, None, None, None),
    ]),
    mkfunc('func2', 'Docstring goes here.', [
      Argument('args', Argument.Type.PositionalRemainder, None, None, None),
      Argument('kwargs', Argument.Type.KeywordRemainder, None, None, None),
    ]),
    mkfunc('func3', 'Docstring goes here.', [
      Argument('kwargs', Argument.Type.KeywordRemainder, None, None, None),
    ]),
    mkfunc('func4', 'Docstring goes here', [
      Argument('abc', Argument.Type.Positional, None, None, None),
    ]),
    mkfunc('func5', 'Docstring goes here', [
      Argument('abc', Argument.Type.Positional, None, None, None),
      Argument('kwonly', Argument.Type.KeywordOnly, None, None, None),
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

  class MyError4(RuntimeError, metaclass=ABCMeta):
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
      bases=['RuntimeError'],
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
