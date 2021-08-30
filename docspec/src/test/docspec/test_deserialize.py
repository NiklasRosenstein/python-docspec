
import docspec
import typing as t
import weakref
from .fixtures import module, typed_module


def test_serialize_typed(typed_module: docspec.Module):
  assert docspec.dump_module(typed_module) == {
    'docstring': None,
    'location': {'filename': 'test.py',
                  'lineno': 0},
    'members': [{'docstring': None,
                  'location': {'filename': 'test.py',
                              'lineno': 1},
                  'name': 'Union',
                  'target': 'typing.Union',
                  'type': 'indirection'},
                {'bases': None,
                  'decorations': None,
                  'docstring': { 'content': 'This is class foo.', 'location': { 'filename': 'test.py', 'lineno': 3 } },
                  'location': {'filename': 'test.py',
                              'lineno': 2},
                  'members': [{'datatype': 'Union[int, float]',
                              'docstring': None,
                              'location': {'filename': 'test.py',
                                            'lineno': 4},
                              'name': 'val',
                              'type': 'data',
                              'value': '42'},
                              {'args': [{'name': 'self',
                                        'type': 'POSITIONAL'}],
                              'decorations': None,
                              'docstring': None,
                              'location': {'filename': 'test.py',
                                            'lineno': 5},
                              'modifiers': None,
                              'name': '__init__',
                              'return_type': None,
                              'type': 'function'}],
                  'metaclass': None,
                  'name': 'foo',
                  'type': 'class'}],
    'name': 'a',
  }


def test_serialize(module: docspec.Module):
  assert docspec.dump_module(module) == {
    'name': 'a',
    'location': None,
    'docstring': None,
    'members': [
      {
        'type': 'class',
        'name': 'foo',
        'location': None,
        'docstring': {
          'content': 'This is class foo.',
          'location': None,
        },
        'members': [
          {
            'type': 'data',
            'name': 'val',
            'location': None,
            'docstring': None,
            'datatype': 'int',
            'value': '42',
          },
          {
            'type': 'function',
            'name': '__init__',
            'location': None,
            'docstring': None,
            'modifiers': None,
            'args': [
              {
                'name': 'self',
                'type': 'POSITIONAL',
              }
            ],
            'return_type': None,
            'decorations': None,
          }
        ],
        'metaclass': None,
        'bases': None,
        'decorations': None,
      }
    ],
  }


def test_serialize_deserialize(module: docspec.Module):
  deser = docspec.load_module(docspec.dump_module(module))
  assert deser == module

  def _deep_comparison(a, b, path, seen):
    assert type(a) == type(b), path
    if isinstance(a, weakref.ref):
      a, b = a(), b()
      assert a == b, path
    assert a == b, path
    if id(a) in seen and id(b) in seen:
      return
    seen.update({id(a), id(b)})
    if hasattr(a, '__dict__'):
      a, b = vars(a), vars(b)
    if isinstance(a, t.Mapping):
      for key in a:
        _deep_comparison(a[key], b[key], path + [key], seen)
    elif isinstance(a, t.Sequence) and not isinstance(a, (bytes, str)):
      for i in range(len(a)):
        _deep_comparison(a[i], b[i], path + [i], seen)

  _deep_comparison(deser, module, ['$'], set())
