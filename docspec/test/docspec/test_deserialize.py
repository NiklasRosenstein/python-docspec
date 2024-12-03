from __future__ import annotations

import typing as t
import weakref

import docspec

loc = docspec.Location("<string>", 0)
s_loc = {"filename": "<string>", "lineno": 0}


def test_serialize_typed(typed_module: docspec.Module) -> None:
    assert docspec.dump_module(typed_module) == {
        "location": {"filename": "test.py", "lineno": 0},
        "members": [
            {
                "location": {"filename": "test.py", "lineno": 1},
                "name": "Union",
                "target": "typing.Union",
                "type": "indirection",
            },
            {
                "docstring": {"content": "This is class foo.", "location": {"filename": "test.py", "lineno": 3}},
                "location": {"filename": "test.py", "lineno": 2},
                "members": [
                    {
                        "datatype": "Union[int, float]",
                        "location": {"filename": "test.py", "lineno": 4},
                        "name": "val",
                        "type": "data",
                        "value": "42",
                    },
                    {
                        "args": [
                            {"name": "self", "type": "POSITIONAL", "location": {"filename": "test.py", "lineno": 5}}
                        ],
                        "location": {"filename": "test.py", "lineno": 5},
                        "name": "__init__",
                        "type": "function",
                    },
                ],
                "name": "foo",
                "type": "class",
                "decorations": [],
            },
        ],
        "name": "a",
    }


def test_serialize(module: docspec.Module) -> None:
    assert docspec.dump_module(module) == {
        "name": "a",
        "location": s_loc,
        "members": [
            {
                "type": "class",
                "name": "foo",
                "location": s_loc,
                "docstring": {
                    "content": "This is class foo.",
                    "location": s_loc,
                },
                "members": [
                    {
                        "type": "data",
                        "name": "val",
                        "location": s_loc,
                        "datatype": "int",
                        "value": "42",
                    },
                    {
                        "type": "function",
                        "name": "__init__",
                        "location": s_loc,
                        "args": [
                            {
                                "location": s_loc,
                                "name": "self",
                                "type": "POSITIONAL",
                            }
                        ],
                    },
                ],
            }
        ],
    }


def test_serialize_deserialize(module: docspec.Module) -> None:
    deser = docspec.load_module(docspec.dump_module(module))
    assert deser == module

    def _deep_comparison(a: t.Any, b: t.Any, path: list[str | int], seen: set[int]) -> None:
        assert isinstance(a, type(b)), path
        if isinstance(a, weakref.ref):
            a, b = a(), b()
            assert a == b, path
        assert a == b, path
        if id(a) in seen and id(b) in seen:
            return
        seen.update({id(a), id(b)})
        if hasattr(a, "__dict__"):
            a, b = vars(a), vars(b)
        if isinstance(a, t.Mapping):
            for key in a:
                _deep_comparison(a[key], b[key], path + [key], seen)
        elif isinstance(a, t.Sequence) and not isinstance(a, (bytes, str)):
            for i in range(len(a)):
                _deep_comparison(a[i], b[i], path + [i], seen)

    _deep_comparison(deser, module, ["$"], set())


def test_deserialize_old_function_argument_types() -> None:
    payload = {
        "name": "a",
        "location": s_loc,
        "docstring": None,
        "members": [
            {
                "type": "function",
                "name": "bar",
                "location": s_loc,
                "docstring": None,
                "modifiers": None,
                "return_type": None,
                "decorations": None,
                "args": [{"location": s_loc, "name": "n", "datatype": "int", "type": "Positional"}],
            }
        ],
    }
    assert docspec.load_module(payload) == docspec.Module(
        name="a",
        location=loc,
        docstring=None,
        members=[
            docspec.Function(
                name="bar",
                location=loc,
                docstring=None,
                modifiers=None,
                return_type=None,
                decorations=None,
                args=[docspec.Argument(location=loc, name="n", datatype="int", type=docspec.Argument.Type.POSITIONAL)],
            )
        ],
    )
