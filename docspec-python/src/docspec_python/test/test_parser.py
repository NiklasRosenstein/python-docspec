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
from docspec_python import parse_python
from functools import wraps
from io import StringIO
from json import dumps
from textwrap import dedent


def unset_location(obj):
  obj.location = None
  for member in getattr(obj, 'members', []):
    unset_location(member)


def docspec_test(**options):
  """
  Decorator for docspec unit tests.
  """

  def decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
      options.setdefault('module_name', func.__name__.lstrip('test_'))
      parsed_module = parse_python(StringIO(dedent(func.__doc__)), **options)
      unset_location(parsed_module)
      reference_module = Module(options['module_name'], None, None, func(*args, **kwargs))
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
