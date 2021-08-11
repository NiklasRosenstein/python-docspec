
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
  return module


def test_reverse_map(module: docspec.Module) -> None:
  rmap = docspec.ReverseMap([module])
  assert rmap.get_parent(module) is None
  assert rmap.get_parent(module.members[0]) is module
