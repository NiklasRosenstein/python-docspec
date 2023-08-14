
import ast
import inspect
import sys
import types
from functools import wraps
from io import StringIO
from json import dumps
from textwrap import dedent
from typing import Any, Callable, List, Optional, TypeVar, Iterable

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

from .test_parser import DocspecTest, mkfunc, unset_location

try:
    from docspec_python import parser2
except ImportError:
    parser2 = None

loc = Location('<test>', 0, None)

def _parse_doc(docstring:str) -> Iterable[parser2.ModSpec]:
    """
    format is 
    '''
    > {'modname':'test', }
    import sys
    import thing
    > {'modname':'test2', }
    from test import thing
    '''
    """
    docstring = '\n'+inspect.cleandoc(docstring)
    # separate modules
    for p in docstring.split('\n>'):
        if not p:
            continue
        try:
            meta, *src = p.splitlines()
        except ValueError as e:
            raise ValueError(f'value is: {p!r}') from e
        parsed_meta = ast.literal_eval(meta)
        assert isinstance(parsed_meta, dict)
        yield parser2.ModSpec(src='\n'.join(src), **parsed_meta)


def docspec_test(parser_options: parser2.ParserOptions | None = None, 
                 strip_locations: bool = True
) -> Callable[[DocspecTest], Callable[[], None]]:
    """
    Decorator for docspec unit tests, parser2.
    """

    def decorator(func: DocspecTest) -> Callable[[], None]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            
            if parser2 is None:
                return
            
            # parse docstring into a series of modules
            mods = list(_parse_doc(func.__doc__ or ""))
            parsed_modules = list(parser2.parse_modules(mods, options=parser_options))
            
            # run test
            expected_modules = func(*args, **kwargs)

            if strip_locations:
                for parsed_module in parsed_modules:
                    unset_location(parsed_module)
                for reference_module in expected_modules:
                    unset_location(reference_module)
            assert dumps([dump_module(r) for r in expected_modules], indent=2) == dumps([dump_module(p) for p in parsed_modules], indent=2)

        return wrapper

    return decorator

@docspec_test(strip_locations=True)
def test_funcdef_annotation_expanded() -> List[_ModuleMemberType]:
    """
    > {'modname':'mod', 'is_package':True}
    from ._impl import Cls
    def a() -> Cls:
        ...
    > {'modname':'mod._impl'}
    class Cls:
        ...
    """
    return [
        Module(
            location=loc, 
            name='mod', 
            docstring=None, 
            members=[
                Indirection(
                    name='Cls',
                    target='mod._impl.Cls',
                    location=loc,
                    docstring=None,
                ),
                Function(
                    name="a",
                    location=loc,
                    docstring=None,
                    modifiers=None,
                    args=[],
                    return_type='mod._impl.Cls',
                    decorations=[],
                )]),
        Module(
            location=loc, 
            name='mod._impl', 
            docstring=None, 
            members=[
                Class(
                    name="Cls",
                    location=loc,
                    docstring=None,
                    members=[],
                    metaclass=None,
                    bases=[],
                    decorations=None,
                )])
    ]

@docspec_test(strip_locations=True, parser_options=parser2.ParserOptions(verbosity=2))
def test_wildcard_imports() -> List[_ModuleMemberType]:
    """
    > {'modname':'mod', 'is_package':True}
    from ._impl import *
    from ._impl2 import *
    from ._impl3 import *
    from ._impl3 import __all__ as _all3
    __all__ = ['Cls2', 'Cls1']
    __all__ += _all3

    def a(x:Cls2, y:Cls5) -> Cls1:
        ...
    > {'modname':'mod._impl'}
    class Cls1:
        ...
    > {'modname':'mod._impl2'}
    class Cls2:
        ...
    > {'modname':'mod._impl3'}
    class Cls3:
        ...
    class Cls4:
        ...
    class Cls5:
        ...
    __all__ = ['Cls3', 'Cls5']
    """
    return [
        Module(
            location=loc, 
            name='mod', 
            docstring=None, 
            members=[
                Indirection(location=loc, name='*', docstring=None, target='mod._impl.*'),
                Indirection(location=loc, name='Cls1', docstring=None, target='mod._impl.Cls1'),
                Indirection(location=loc, name='*', docstring=None, target='mod._impl2.*'),
                Indirection(location=loc, name='Cls2', docstring=None, target='mod._impl2.Cls2'),
                Indirection(location=loc, name='*', docstring=None, target='mod._impl3.*'),
                Indirection(location=loc, name='Cls3', docstring=None, target='mod._impl3.Cls3'),
                Indirection(location=loc, name='Cls5', docstring=None, target='mod._impl3.Cls5'),
                Indirection(location=loc, name='_all3', docstring=None, target='mod._impl3.__all__'),
                Variable(location=loc, name='__all__', docstring=None, value="['Cls2', 'Cls1', 'Cls3', 'Cls5']"),
                Function(location=loc, name='a', modifiers=None, args=[
                    Argument(location=loc, name='x', type=Argument.Type.POSITIONAL, 
                             datatype='mod._impl2.Cls2'), 
                    Argument(location=loc, name='y', type=Argument.Type.POSITIONAL, 
                             datatype='mod._impl3.Cls5'), 
                ], return_type='mod._impl.Cls1', docstring=None, decorations=[]),
            ]),
        Module(
            location=loc, 
            name='mod._impl', 
            docstring=None, 
            members=[
                Class(location=loc, name='Cls1', docstring=None,
                      members=[], metaclass=None, bases=[], decorations=None),
            ]),
        Module(
            location=loc, 
            name='mod._impl2', 
            docstring=None, 
            members=[
                Class(location=loc, name='Cls2', docstring=None,
                      members=[], metaclass=None, bases=[], decorations=None),
            ]),
        Module(
            location=loc, 
            name='mod._impl3', 
            docstring=None, 
            members=[
                Class(location=loc, name='Cls3', docstring=None,
                      members=[], metaclass=None, bases=[], decorations=None),
                Class(location=loc, name='Cls4', docstring=None,
                      members=[], metaclass=None, bases=[], decorations=None),
                Class(location=loc, name='Cls5', docstring=None,
                      members=[], metaclass=None, bases=[], decorations=None),
                Variable(location=loc, name='__all__', docstring=None, value="['Cls3', 'Cls5']")
            ])
    ]