
import docspec
import pytest


@pytest.fixture
def module() -> docspec.Module:
  module = docspec.Module('a', None, None, [
    docspec.Class('foo', None, 'This is class foo.', None, None, None, [
      docspec.Data('val', None, None, 'int', '42'),
      docspec.Function('__init__', None, None, None, [
        docspec.Argument('self', docspec.Argument.Type.Positional, None, None, None)
      ], None, None),
    ]),
  ])
  module.sync_hierarchy()
  return module


@pytest.fixture
def typed_module() -> docspec.Module:
  module = docspec.Module('a', docspec.Location('test.py', 0), None, [
    docspec.Indirection('Union', docspec.Location('test.py', 1), None, 'typing.Union'),
    docspec.Class('foo', docspec.Location('test.py', 2), 'This is class foo.', None, None, None, [
      docspec.Data('val', docspec.Location('test.py', 4), None, 'Union[int, float]', '42'),
      docspec.Function('__init__', docspec.Location('test.py', 5), None, None, [
        docspec.Argument('self', docspec.Argument.Type.Positional, None, None, None)
      ], None, None),
    ]),
  ])
  module.sync_hierarchy()
  return module
