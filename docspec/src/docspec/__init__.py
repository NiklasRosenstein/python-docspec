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
__version__ = '0.0.3'
__all__ = [
  'Location',
  'Module',
  'Class',
  'Data',
  'Function',
  'Argument',
  'Decoration',
  'load_module',
  'load_modules',
  'dump_module'
]


from nr.databind.core import Field, ObjectMapper, ProxyType, Struct, UnionType
from nr.databind.json import JsonModule
from typing import Dict, Iterable, Optional, TextIO, Union
import enum
import io
import json

_ClassProxy = ProxyType()
_mapper = ObjectMapper(JsonModule())


class Location(Struct):
  filename = Field(str)
  lineno = Field(int)


class Decoration(Struct):
  name = Field(str)
  args = Field([str], nullable=True)


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


class _Base(Struct):
  name = Field(str, prominent=True)
  location = Field(Location, nullable=True)
  docstring = Field(str, nullable=True)


class Data(_Base):
  datatype = Field(str, nullable=True)
  value = Field(str, nullable=True)


class Function(_Base):
  modifiers = Field([str], nullable=True)
  args = Field([Argument])
  return_type = Field(str, nullable=True)
  decorations = Field([Decoration], nullable=True)


@_ClassProxy.implementation
class Class(_Base):
  metaclass = Field(str, nullable=True)
  bases = Field([str], nullable=True)
  decorations = Field([Decoration], nullable=True)
  members = Field([UnionType({
    'data': Data,
    'function': Function,
    'class': _ClassProxy
  })])


class Module(_Base):
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
  Dumps a module to the specified target or returns it as plain structured
  data.
  """

  if isinstance(target, str):
    with open(target, 'w') as fp:
      dump_module(module, fp, dumper)
    return None

  data = _mapper.serialize(module, Module)
  if target:
    dumper(data, target)
  else:
    return data
