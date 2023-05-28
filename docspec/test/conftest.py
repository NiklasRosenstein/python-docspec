import pytest

import docspec

loc = docspec.Location("<string>", 0, None)


@pytest.fixture
def module() -> docspec.Module:
    module = docspec.Module(
        loc,
        "a",
        None,
        [
            docspec.Class(
                loc,
                "foo",
                docspec.Docstring(loc, "This is class foo."),
                [
                    docspec.Variable(loc, "val", None, "int", "42"),
                    docspec.Function(
                        loc,
                        "__init__",
                        None,
                        None,
                        [docspec.Argument(loc, "self", docspec.Argument.Type.POSITIONAL)],
                        None,
                        None,
                    ),
                ],
                None,
                None,
                None,
            ),
        ],
    )
    module.sync_hierarchy()
    return module


@pytest.fixture
def typed_module() -> docspec.Module:
    module = docspec.Module(
        docspec.Location("test.py", 0),
        "a",
        None,
        [
            docspec.Indirection(docspec.Location("test.py", 1), "Union", None, "typing.Union"),
            docspec.Class(
                docspec.Location("test.py", 2),
                "foo",
                docspec.Docstring(docspec.Location("test.py", 3), "This is class foo."),
                [
                    docspec.Variable(docspec.Location("test.py", 4), "val", None, "Union[int, float]", "42"),
                    docspec.Function(
                        docspec.Location("test.py", 5),
                        "__init__",
                        None,
                        None,
                        [docspec.Argument(docspec.Location("test.py", 5), "self", docspec.Argument.Type.POSITIONAL)],
                        None,
                        None,
                    ),
                ],
                None,
                None,
                [],
            ),
        ],
    )
    module.sync_hierarchy()
    return module
