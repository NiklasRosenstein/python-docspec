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

__author__ = 'Niklas Rosenstein <rosensteinniklas@gmail.com>'
__version__ = '0.1.0'
__all__ = [
  'Location',
  'Decoration',
  'Argument',
  'ApiObject',
  'Data',
  'Function',
  'Class',
  'Module',
  'load_module',
  'load_modules',
  'dump_module',
  'filter_visit',
  'visit',
  'ReverseMap',
  'get_member',
]


from nr.databind.core import Field, ObjectMapper, ProxyType, Struct, UnionType
from nr.databind.json import JsonModule
from typing import Any, Callable, Dict, Iterable, List, Optional, TextIO, Union
import enum
import io
import json

_ClassProxy = ProxyType()
_mapper = ObjectMapper(JsonModule())


class Location(Struct):
  filename = Field(str, nullable=True)
  lineno = Field(int)


class Decoration(Struct):
  name = Field(str)
  args = Field(str, nullable=True)


class Argument(Struct):
  class Type(enum.Enum):
    PositionalOnly = 0
    Positional = 1
    PositionalRemainder = 2
    KeywordOnly = 3
    KeywordRemainder = 4
  name = Field(str)
  type = Field(Type)
  decorations = Field([Decoration], nullable=True)
  datatype = Field(str, nullable=True)
  default_value = Field(str, nullable=True)


class ApiObject(Struct):
  name = Field(str, prominent=True)
  location = Field(Location, nullable=True)
  docstring = Field(str, nullable=True)


class Data(ApiObject):
  datatype = Field(str, nullable=True)
  value = Field(str, nullable=True)


class Function(ApiObject):
  modifiers = Field([str], nullable=True)
  args = Field([Argument])
  return_type = Field(str, nullable=True)
  decorations = Field([Decoration], nullable=True)


@_ClassProxy.implementation
class Class(ApiObject):
  metaclass = Field(str, nullable=True)
  bases = Field([str], nullable=True)
  decorations = Field([Decoration], nullable=True)
  members = Field([UnionType({
    'data': Data,
    'function': Function,
    'class': _ClassProxy
  })])


class Module(ApiObject):
  members = Field([UnionType({
    'data': Data,
    'class': Class,
    'function': Function,
  })])


def load_module(
    source: Union[str, TextIO, Dict],
    filename: str = None,
    loader = json.load
) -> Module:
  """
  Loads a #Module from the specified *source*, which may be either a filename,
  a file-like object to read from or plain structured data.

  :param source: The JSON source to load the module from.
  :param filename: The name of the source. This will be displayed in error
    messages if the deserialization fails.
  :param loader: A function for loading plain structured data from a file-like
    object. Defaults to #json.load().
  """

  filename = filename or getattr(source, 'name', None)

  if isinstance(source, str):
    with open(source) as fp:
      return load_module(fp, source, loader)
  elif hasattr(source, 'read'):
    source = loader(source)

  return _mapper.deserialize(source, Module, filename=filename)


def load_modules(
    source: Union[str, TextIO, Iterable[Dict]],
    filename: str = None,
    loader = json.load
) -> Iterable[Module]:
  """
  Loads a stream of modules from the specified *source*. Similar to
  #load_module(), the *source* can be a filename, file-like object or a
  list of plain structured data to deserialize from.
  """

  filename = filename or getattr(source, 'name', None)

  if isinstance(source, str):
    with open(source) as fp:
      yield from load_modules(fp, source, loader)
    return
  elif hasattr(source, 'read'):
    source = (loader(io.StringIO(line)) for line in source)

  for data in source:
    yield _mapper.deserialize(data, Module, filename=filename)


def dump_module(
    module: Module,
    target: Union[str, TextIO] = None,
    dumper = json.dump
) -> Optional[Dict]:
  """
  Dumps a module to the specified target or returns it as plain structured data.
  """

  if isinstance(target, str):
    with open(target, 'w') as fp:
      dump_module(module, fp, dumper)
    return None

  data = _mapper.serialize(module, Module)
  if target:
    dumper(data, target)
    target.write('\n')
  else:
    return data


def filter_visit(
  objects: List[ApiObject],
  predicate: Callable[[ApiObject], bool],
  order: str = 'pre',
) -> None:
  """
  Visits all *objects* recursively, applying the *predicate* in the specified *order*. If
  the predicate returrns #False, the object will be removed from it's containing list.

  If an object is removed in pre-order, it's members will not be visited.

  :param objects: A list of objects to visit recursively. This list will be modified if
    the *predicate* returns #False for an object.
  :param predicate: The function to apply over all visited objects.
  :param order: The order in which the objects are visited. The default order is `'pre'`
    in which case the *predicate* is called before visiting the object's members. The
    order may also be `'post'`.
  """

  if order not in ('pre', 'post'):
    raise ValueError('invalid order: {!r}'.format(order))

  offset = 0
  for index in range(len(objects)):
    if order == 'pre':
      if not predicate(objects[index - offset]):
        del objects[index - offset]
        offset += 1
        continue
    filter_visit(getattr(objects[index - offset], 'members', []), predicate, order)
    if order == 'post':
      if not predicate(objects[index - offset]):
        del objects[index - offset]
        offset += 1


def visit(
  objects: List[ApiObject],
  func: Callable[[ApiObject], Any],
  order: str = 'pre',
) -> None:
  """
  Visits all *objects*, applying *func* in the specified *order*.
  """

  filter_visit(objects, (lambda obj: func(obj) or True), order)


class ReverseMap:
  """
  Reverse map for finding the parent of an #ApiObject.
  """

  def __init__(self, modules: List[Module]) -> None:
    self._modules = modules
    self._reverse_map = {}
    for module in modules:
      self._init(module, None)

  def _init(self, obj: ApiObject, parent: Optional[ApiObject]) -> None:
    self._reverse_map[id(obj)] = parent
    for member in getattr(obj, 'members', []):
      self._init(member, obj)

  def get_parent(self, obj: ApiObject) -> Optional[ApiObject]:
    try:
      return self._reverse_map[id(obj)]
    except KeyError:
      raise KeyError(obj)

  def path(self, obj: ApiObject) -> List[ApiObject]:
    result = []
    while obj:
      result.append(obj)
      obj = self.get_parent(obj)
    result.reverse()
    return result


def get_member(obj: ApiObject, name: str) -> Optional[ApiObject]:
  """
  Generic function to retrieve a member from an API object. This will always return #None for
  objects that don't support members (eg. #Function and #Data).
  """

  for member in getattr(obj, 'member', []):
    if member.name == name:
      return member
  return None
