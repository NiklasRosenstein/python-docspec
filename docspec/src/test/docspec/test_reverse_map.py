
import docspec
from .fixtures import module


def test_reverse_map(module: docspec.Module) -> None:
  rmap = docspec.ReverseMap([module])
  assert rmap.get_parent(module) is None
  assert rmap.get_parent(module.members[0]) is module
