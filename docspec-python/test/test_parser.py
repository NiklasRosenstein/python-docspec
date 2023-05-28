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

from __future__ import annotations

import sys
from functools import wraps
from io import StringIO
from json import dumps
from textwrap import dedent
from typing import Any, Callable, List, Optional, TypeVar

import pytest
from docspec import (
    ApiObject,
    Argument,
    Class,
    Decoration,
    Docstring,
    Function,
    HasLocation,
    HasMembers,
    Indirection,
    Location,
    Module,
    Variable,
    _ModuleMemberType,
    dump_module,
)
from nr.util.inspect import get_callsite

from docspec_python import ParserOptions, format_arglist, parse_python_module

T = TypeVar("T")
DocspecTest = Callable[[], List[_ModuleMemberType]]
loc = Location("<string>", 0, None)


def mkfunc(
    name: str,
    docstring: Optional[str],
    lineno: int,
    args: List[Argument],
    modifiers: Optional[List[str]] = None,
    return_type: Optional[str] = None,
) -> Function:
    return Function(
        name=name,
        location=loc,
        docstring=Docstring(Location(get_callsite().code_name, lineno), docstring) if docstring else None,
        modifiers=modifiers,
        args=args,
        return_type=return_type,
        decorations=[],
    )


def unset_location(obj: HasLocation) -> None:
    if isinstance(obj, HasLocation):
        obj.location = loc
    if isinstance(obj, ApiObject) and obj.docstring:
        unset_location(obj.docstring)
    if isinstance(obj, HasMembers):
        for member in obj.members:
            unset_location(member)
    elif isinstance(obj, Function):
        for arg in obj.args:
            unset_location(arg)


def docspec_test(
    module_name: str | None = None, parser_options: ParserOptions | None = None, strip_locations: bool = True
) -> Callable[[DocspecTest], Callable[[], None]]:
    """
    Decorator for docspec unit tests.
    """

    def decorator(func: DocspecTest) -> Callable[[], None]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            parsed_module = parse_python_module(
                StringIO(dedent(func.__doc__ or "")),
                module_name=module_name or func.__name__.lstrip("test_"),
                options=parser_options,
                filename=func.__name__,
            )
            parsed_module.location = loc
            reference_module = Module(
                name=parsed_module.name, location=loc, docstring=None, members=func(*args, **kwargs)
            )
            if strip_locations:
                unset_location(parsed_module)
                unset_location(reference_module)
            assert dumps(dump_module(reference_module), indent=2) == dumps(dump_module(parsed_module), indent=2)

        return wrapper

    return decorator


@docspec_test()
def test_funcdef_1() -> List[_ModuleMemberType]:
    """
    def a():
      ' A simple function. '
    """

    return [
        Function(
            name="a",
            location=loc,
            docstring=Docstring(Location("test_funcdef_1", 2), "A simple function."),
            modifiers=None,
            args=[],
            return_type=None,
            decorations=[],
        )
    ]


@docspec_test()
def test_funcdef_2() -> List[_ModuleMemberType]:
    """
    def b(a: int, *, c: str, **opts: Any) -> None:
      ' This uses annotations and keyword-only arguments. '
    """

    return [
        Function(
            name="b",
            location=loc,
            docstring=Docstring(Location("test_funcdef_2", 2), "This uses annotations and keyword-only arguments."),
            modifiers=None,
            args=[
                Argument(loc, "a", Argument.Type.POSITIONAL, None, "int", None),
                Argument(loc, "c", Argument.Type.KEYWORD_ONLY, None, "str", None),
                Argument(loc, "opts", Argument.Type.KEYWORD_REMAINDER, None, "Any", None),
            ],
            return_type="None",
            decorations=[],
        )
    ]


@docspec_test()
def test_funcdef_3() -> List[_ModuleMemberType]:
    """
    @classmethod
    @db_session(sql_debug=True)
    def c(self, a: int, b, *args, opt: str) -> Optional[int]:
      ' More arg variations. '
    """

    return [
        Function(
            name="c",
            location=loc,
            docstring=Docstring(Location("test_funcdef_3", 4), "More arg variations."),
            modifiers=None,
            args=[
                Argument(loc, "self", Argument.Type.POSITIONAL, None, None, None),
                Argument(loc, "a", Argument.Type.POSITIONAL, None, "int", None),
                Argument(loc, "b", Argument.Type.POSITIONAL, None, None, None),
                Argument(loc, "args", Argument.Type.POSITIONAL_REMAINDER, None, None, None),
                Argument(loc, "opt", Argument.Type.KEYWORD_ONLY, None, "str", None),
            ],
            return_type="Optional[int]",
            decorations=[
                Decoration(Location("test_funcdef_3", 2), "classmethod", None),
                Decoration(Location("test_funcdef_3", 3), "db_session", "(sql_debug=True)"),
            ],
        )
    ]


@docspec_test()
def test_funcdef_4() -> List[_ModuleMemberType]:
    """
    def fun(project_name, project_type, port=8001):
      pass
    """

    return [
        Function(
            name="fun",
            location=loc,
            docstring=None,
            modifiers=None,
            args=[
                Argument(loc, "project_name", Argument.Type.POSITIONAL, None, None, None),
                Argument(loc, "project_type", Argument.Type.POSITIONAL, None, None, None),
                Argument(loc, "port", Argument.Type.POSITIONAL, None, None, "8001"),
            ],
            return_type=None,
            decorations=[],
        )
    ]


@docspec_test(parser_options=ParserOptions(treat_singleline_comment_blocks_as_docstrings=True))
def test_funcdef_5_single_stmt() -> List[_ModuleMemberType]:
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

    args = [Argument(loc, "self", Argument.Type.POSITIONAL, None, None, None)]
    return [
        mkfunc("func1", None, 1, args),
        mkfunc("func2", "ABC\n  DEF", 4, args),
        mkfunc("func3", "ABC\nDEF", 9, args),
        mkfunc("func4", "ABC\n  DEF", 14, args),
    ]


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6 or higher")
@docspec_test()
def test_funcdef_6_starred_args() -> List[_ModuleMemberType]:
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

    async def func6(cls, *fs, loop=None, timeout=None, total=None, **tqdm_kwargs):
      ''' Docstring goes here. '''
    """

    return [
        mkfunc(
            "func1",
            None,
            0,
            [
                Argument(loc, "a", Argument.Type.POSITIONAL, None, None, None),
                Argument(loc, "b", Argument.Type.KEYWORD_ONLY, None, None, None),
                Argument(loc, "c", Argument.Type.KEYWORD_REMAINDER, None, None, None),
            ],
        ),
        mkfunc(
            "func2",
            "Docstring goes here.",
            4,
            [
                Argument(loc, "args", Argument.Type.POSITIONAL_REMAINDER, None, None, None),
                Argument(loc, "kwargs", Argument.Type.KEYWORD_REMAINDER, None, None, None),
            ],
        ),
        mkfunc(
            "func3",
            "Docstring goes here.",
            7,
            [
                Argument(loc, "kwargs", Argument.Type.KEYWORD_REMAINDER, None, None, None),
            ],
        ),
        mkfunc(
            "func4",
            "Docstring goes here",
            10,
            [
                Argument(loc, "abc", Argument.Type.POSITIONAL, None, None, None),
            ],
        ),
        mkfunc(
            "func5",
            "Docstring goes here",
            13,
            [
                Argument(loc, "abc", Argument.Type.POSITIONAL, None, None, None),
                Argument(loc, "kwonly", Argument.Type.KEYWORD_ONLY, None, None, None),
            ],
        ),
        mkfunc(
            "func6",
            "Docstring goes here.",
            16,
            [
                Argument(loc, "cls", Argument.Type.POSITIONAL, None, None, None),
                Argument(loc, "fs", Argument.Type.POSITIONAL_REMAINDER, None, None, None),
                Argument(loc, "loop", Argument.Type.KEYWORD_ONLY, None, None, "None"),
                Argument(loc, "timeout", Argument.Type.KEYWORD_ONLY, None, None, "None"),
                Argument(loc, "total", Argument.Type.KEYWORD_ONLY, None, None, "None"),
                Argument(loc, "tqdm_kwargs", Argument.Type.KEYWORD_REMAINDER, None, None, None),
            ],
            ["async"],
        ),
    ]


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@docspec_test()
def test_funcdef_7_posonly_args() -> List[_ModuleMemberType]:
    """
    def func1(x, y=3, /, z=5, w=7): pass
    def func2(x, /, *v, a=1, b=2): pass
    def func3(x, /, *, a=1, b=2, **kwargs): pass
    def func4(x, y, /): pass
    """

    return [
        mkfunc(
            "func1",
            None,
            1,
            [
                Argument(loc, "x", Argument.Type.POSITIONAL_ONLY),
                Argument(loc, "y", Argument.Type.POSITIONAL_ONLY, default_value="3"),
                Argument(loc, "z", Argument.Type.POSITIONAL, default_value="5"),
                Argument(loc, "w", Argument.Type.POSITIONAL, default_value="7"),
            ],
        ),
        mkfunc(
            "func2",
            None,
            2,
            [
                Argument(loc, "x", Argument.Type.POSITIONAL_ONLY),
                Argument(loc, "v", Argument.Type.POSITIONAL_REMAINDER),
                Argument(loc, "a", Argument.Type.KEYWORD_ONLY, default_value="1"),
                Argument(loc, "b", Argument.Type.KEYWORD_ONLY, default_value="2"),
            ],
        ),
        mkfunc(
            "func3",
            None,
            3,
            [
                Argument(loc, "x", Argument.Type.POSITIONAL_ONLY),
                Argument(loc, "a", Argument.Type.KEYWORD_ONLY, default_value="1"),
                Argument(loc, "b", Argument.Type.KEYWORD_ONLY, default_value="2"),
                Argument(loc, "kwargs", Argument.Type.KEYWORD_REMAINDER),
            ],
        ),
        mkfunc(
            "func4",
            None,
            3,
            [
                Argument(loc, "x", Argument.Type.POSITIONAL_ONLY),
                Argument(loc, "y", Argument.Type.POSITIONAL_ONLY),
            ],
        ),
    ]


@docspec_test()
def test_classdef_1_exceptions() -> List[_ModuleMemberType]:
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
        Class(name="MyError1", location=loc, docstring=None, metaclass=None, bases=[], decorations=None, members=[]),
        Class(name="MyError2", location=loc, docstring=None, metaclass=None, bases=[], decorations=None, members=[]),
        Class(
            name="MyError3",
            location=loc,
            docstring=None,
            metaclass=None,
            bases=["RuntimeError"],
            decorations=None,
            members=[],
        ),
        Class(
            name="MyError4",
            location=loc,
            docstring=None,
            metaclass="ABCMeta",
            bases=["RuntimeError", "object"],
            decorations=None,
            members=[],
        ),
        Class(
            name="MyError5", location=loc, docstring=None, metaclass="ABCMeta", bases=[], decorations=None, members=[]
        ),
        Class(
            name="MyError6",
            location=loc,
            docstring=None,
            metaclass="ABCMeta",
            bases=["RuntimeError"],
            decorations=None,
            members=[],
        ),
    ]


@docspec_test(strip_locations=False)
def test_indirections() -> List[_ModuleMemberType]:
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
        Indirection(Location("test_indirections", 2), "os", None, "os"),
        Indirection(Location("test_indirections", 3), "r", None, "urllib.request"),
        Indirection(Location("test_indirections", 4), "path", None, "os.path"),
        Indirection(Location("test_indirections", 4), "sys", None, "sys"),
        Indirection(Location("test_indirections", 4), "P", None, "pathlib"),
        Indirection(Location("test_indirections", 5), "platform", None, "sys.platform"),
        Indirection(Location("test_indirections", 5), "EXE", None, "sys.executable"),
        Indirection(Location("test_indirections", 6), "*", None, "os.path.*"),
        Indirection(Location("test_indirections", 8), "PP", None, "pathlib.PurePath"),
        Indirection(Location("test_indirections", 9), "PosixPath", None, "pathlib.PosixPath"),
        Indirection(Location("test_indirections", 11), "core", None, "..core"),
        Indirection(Location("test_indirections", 12), "Widget", None, "..core.Widget"),
        Indirection(Location("test_indirections", 12), "View", None, "..core.View"),
        Indirection(Location("test_indirections", 13), "pkg_resources", None, ".vendor.pkg_resources"),
        Indirection(Location("test_indirections", 13), "six", None, ".vendor.six"),
        Indirection(Location("test_indirections", 14), "*", None, "...api.*"),
        Function(Location("test_indirections", 15), "foo", None, None, [], None, []),
        Class(
            Location("test_indirections", 17),
            "bar",
            None,
            [
                Indirection(Location("test_indirections", 18), "os", None, "os"),
                Indirection(Location("test_indirections", 19), "dirname", None, "os.path.dirname"),
            ],
            None,
            [],
            None,
        ),
    ]


def test_format_arglist() -> None:
    func = mkfunc(
        "func6",
        "Docstring goes here.",
        16,
        [
            Argument(loc, "cls", Argument.Type.POSITIONAL, None, None, None),
            Argument(loc, "fs", Argument.Type.POSITIONAL_REMAINDER, None, None, None),
            Argument(loc, "loop", Argument.Type.KEYWORD_ONLY, None, None, "None"),
            Argument(loc, "timeout", Argument.Type.KEYWORD_ONLY, None, None, "None"),
            Argument(loc, "total", Argument.Type.KEYWORD_ONLY, None, None, "None"),
            Argument(loc, "tqdm_kwargs", Argument.Type.KEYWORD_REMAINDER, None, None, None),
        ],
        ["async"],
    )
    assert format_arglist(func.args, True) == "cls, *fs, loop=None, timeout=None, total=None, **tqdm_kwargs"


@docspec_test()
def test_funcdef_with_trailing_comma() -> List[_ModuleMemberType]:
    """
    def build_docker_image(
        name: str = "buildDocker",
        default: bool = False,
        dockerfile: str = "docker/release.Dockerfile",
        project: Project | None = None,
        auth: dict[str, tuple[str, str]] | None = None,
        secrets: dict[str, str] | None = None,
        image_qualifier: str | None = None,
        platforms: list[str] | None = None,
        **kwargs: Any,
    ) -> Task:
        pass
    """

    return [
        mkfunc(
            "build_docker_image",
            None,
            0,
            [
                Argument(loc, "name", Argument.Type.POSITIONAL, None, "str", '"buildDocker"'),
                Argument(loc, "default", Argument.Type.POSITIONAL, None, "bool", "False"),
                Argument(loc, "dockerfile", Argument.Type.POSITIONAL, None, "str", '"docker/release.Dockerfile"'),
                Argument(loc, "project", Argument.Type.POSITIONAL, None, "Project | None", "None"),
                Argument(loc, "auth", Argument.Type.POSITIONAL, None, "dict[str, tuple[str, str]] | None", "None"),
                Argument(loc, "secrets", Argument.Type.POSITIONAL, None, "dict[str, str] | None", "None"),
                Argument(loc, "image_qualifier", Argument.Type.POSITIONAL, None, "str | None", "None"),
                Argument(loc, "platforms", Argument.Type.POSITIONAL, None, "list[str] | None", "None"),
                Argument(loc, "kwargs", Argument.Type.KEYWORD_REMAINDER, None, "Any", None),
            ],
            return_type="Task",
        ),
    ]


@docspec_test()
def test_funcdef_with_match_statement() -> List[_ModuleMemberType]:
    """
    def f(x):
        match x:
            case str(s):
                return "string"
            case Path() as p:
                return "path"
            case int(n) | float(n):
                return "number"
            case _:
                return "idk"
    """

    return [
        mkfunc(
            "f",
            None,
            0,
            [
                Argument(loc, "x", Argument.Type.POSITIONAL, None),
            ],
        ),
    ]


@docspec_test(strip_locations=True)
def test_can_parse_raw_docstring() -> List[_ModuleMemberType]:
    r"""
    def normal():
      ' Normal d\\cstring. '

    def single():
      r' S\\ngle raw docstring. '

    def multi():
      r''' M\\lti raw docstring. '''

    def special_characters():
      ''' ﬀ '''
    """

    return [
        mkfunc("normal", "Normal d\\cstring.", 0, []),
        mkfunc("single", "S\\\\ngle raw docstring.", 0, []),
        mkfunc("multi", "M\\\\lti raw docstring.", 0, []),
        mkfunc("special_characters", "ﬀ", 0, []),
    ]


@docspec_test(strip_locations=True)
def test_can_detect_docstrings_after_declarations() -> List[_ModuleMemberType]:
    """
    class Test:
      a: int
      ''' This attribute is important. '''

      #: And so is this.
      b: str
    """

    return [
        Class(
            loc,
            "Test",
            None,
            [
                Variable(
                    loc,
                    "a",
                    Docstring(loc, "This attribute is important."),
                    "int",
                ),
                Variable(
                    loc,
                    "b",
                    Docstring(loc, "And so is this."),
                    "str",
                ),
            ],
            None,
            [],
            None,
        )
    ]


@docspec_test(strip_locations=True)
def test_can_parse_tuple_unpacking() -> List[_ModuleMemberType]:
    """
    v = 42

    a, b = 0, 1  #: This documents a and b.

    #: This documents c and d.
    c, *d = it

    e, (f, *g) = value
    """

    # NOTE(NiklasRosenstein): We don't explicitly support yielding information about variables
    #   resulting from tuple-unpacking as we cannot tell which of the variables the docstring is
    #   for, and how to assign the right side to the variables on the left.

    return [Variable(loc, "v", None, None, "42")]


@docspec_test(strip_locations=True)
def test_can_parse_docstrings_on_same_line() -> List[_ModuleMemberType]:
    """
    a: int = 42 #: This is a variable.

    class Test:
      b: str #: This is b variable.

    #: This takes precedence!
    c: float #: This is c variable.

    d: None  #: This is also ignored.
    ''' Because I exist! '''
    """

    return [
        Variable(loc, "a", Docstring(loc, "This is a variable."), "int", "42"),
        Class(
            loc,
            "Test",
            None,
            [
                Variable(loc, "b", Docstring(loc, "This is b variable."), "str"),
            ],
            None,
            [],
            None,
        ),
        Variable(loc, "c", Docstring(loc, "This takes precedence!"), "float"),
        Variable(loc, "d", Docstring(loc, "Because I exist!"), "None"),
    ]


@docspec_test(strip_locations=True)
def test_hash_docstring_does_not_loose_indentation() -> List[_ModuleMemberType]:
    """
    #: Represents this command:
    #:
    #:    $ bash ./install.sh
    #:
    #:Ok?
    command = ["bash", "./install.sh"]
    """

    return [
        Variable(
            loc,
            "command",
            Docstring(
                loc,
                dedent(
                    """
      Represents this command:

         $ bash ./install.sh

      Ok?
      """
                ).strip(),
            ),
            None,
            '["bash", "./install.sh"]',
        )
    ]


@docspec_test(strip_locations=True)
def test_docstring_does_not_loose_indentation() -> List[_ModuleMemberType]:
    """
    def foo():
      '''
      Example:

          assert 42 == "Answer to the universe"
      '''
    """

    return [
        mkfunc(
            "foo",
            dedent(
                """
      Example:

          assert 42 == "Answer to the universe"
      """
            ).strip(),
            0,
            [],
        )
    ]


@docspec_test(strip_locations=True)
def test_octal_escape_sequence() -> List[_ModuleMemberType]:
    r"""
    def my_example():
        'This is supposed to be pound: \043'
        pass
    """

    return [mkfunc("my_example", "This is supposed to be pound: #", 0, [])]
