# -*- coding: utf8 -*-
# Copyright (c) 2021 Niklas Rosenstein
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
__version__ = '1.0.2'
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

import dataclasses
import enum
import io
import json
import sys
import types
import typing as t
import typing_extensions as te
import weakref

import deprecated
import databind.core.annotations as A
import databind.json

try:
  from termcolor import colored
except ImportError as exc:
  def colored(s, *args, **kwargs):  # type: ignore
    return str(s)

from . import genericvisitor

@dataclasses.dataclass
class Location:
  """
  Represents the location of an #ApiObject by a filename and line number.
  """

  filename: t.Optional[str]
  lineno: int


@dataclasses.dataclass
class Decoration:
  """
  Represents a decorator on a #Class or #Function.
  """

  #: The name of the decorator (i.e. the text between the `@` and `(`).
  name: str

  #: Decorator arguments as plain code (including the leading and trailing parentheses). This is
  #: `None` when the decorator does not have call arguments.
  args: t.Optional[str] = None


@dataclasses.dataclass
class Argument:
  """
  Represents a #Function argument.
  """

  class Type(enum.Enum):
    """
    The type of the argument. This is currently very Python-centric, however most other languages should be able
    to represent the various argument types with a subset of these types without additions (e.g. Java or TypeScript
    only support #Positional and #PositionalRemainder arguments).
    """

    #: A positional only argument. Such arguments are denoted in Python like this: `def foo(a, b, /): ...`
    PositionalOnly = 0

    #: A positional argument, which may also be given as a keyword argument. Basically that is just a normal
    #: argument as you would see most commonly in Python function definitions.
    Positional = 1

    #: An argument that denotes the capture of additional positional arguments, aka. "args" or "varags".
    PositionalRemainder = 2

    #: A keyword-only argument is denoted in Python like thisL `def foo(*, kwonly): ...`
    KeywordOnly = 3

    #: An argument that captures additional keyword arguments, aka. "kwargs".
    KeywordRemainder = 4

  #: The name of the argument.
  name: str

  #: The argument type.
  type: Type

  #: A list of argument decorations. Python does not actually support decorators on function arguments
  #: like for example Java does. This is probably premature to add into the API, but hey, here it is.
  decorations: t.Optional[t.List[Decoration]] = None

  #: The datatype/type annotation of this argument as a code string.
  datatype: t.Optional[str] = None

  #: The default value of the argument as a code string.
  default_value: t.Optional[str] = None


@dataclasses.dataclass
class ApiObject:
  """
  The base class for representing "API Objects". Any API object is any addressable entity in code,
  be that a variable/constant, function, class or module.
  """

  #: The name of the entity. This is usually relative to the respective parent of the entity,
  #: as opposed to it's fully qualified name/absolute name. However, that is more of a
  #: recommendation than rule. For example the #docspec_python loader by default returns
  #: #Module objects with their full module name (and does not create a module hierarchy).
  name: str

  #: The location of the API object, i.e. where it is sourced from/defined in the code.
  location: t.Optional[Location] = dataclasses.field(repr=False)

  #: The documentation string of the API object.
  docstring: t.Optional[str] = dataclasses.field(repr=False)

  def __post_init__(self) -> None:
    self._parent: t.Optional['weakref.ReferenceType[HasMembers]'] = None

  @property
  def parent(self) -> t.Optional['HasMembers']:
    """
    Returns the parent of the #HasMembers. Note that if you make any modifications to the API object tree,
    you will need to call #sync_hierarchy() afterwards because adding to #Class.members or #Module.members
    does not automatically keep the #parent property in sync.
    """

    if self._parent is not None:
      parent = self._parent()
      if parent is None:
        raise RuntimeError(f'lost reference to parent object')
    else:
      parent = None
    return parent

  @parent.setter
  def parent(self, parent: t.Optional['HasMembers']) -> None:
    if parent is not None:
      self._parent = weakref.ref(parent)
    else:
      self._parent = None

  @property
  def path(self) -> t.List['ApiObject']:
    """
    Returns a list of all of this API object's parents, from top to bottom. The list includes *self* as the
    last item.
    """

    result = []
    current: t.Optional[ApiObject] = self
    while current:
      result.append(current)
      current = current.parent
    result.reverse()
    return result

  def sync_hierarchy(self, parent: t.Optional['HasMembers'] = None) -> None:
    """
    Synchronize the hierarchy of this API object and all of it's children. This should be called when the
    #HasMembers.members are updated to ensure that all child objects reference the right #parent. Loaders
    are expected to return #ApiObject#s in a fully synchronized state such that the user does not have to
    call this method unless they are doing modifications to the tree.
    """

    self.parent = parent

  def _get_children(self) -> t.Iterable['ApiObject']:
    if isinstance(self, HasMembers): return self.members
    else: return ()
  def walk(self, v: genericvisitor.Visitor['ApiObject']) -> None:
    """See #genericvisitor.walk"""
    genericvisitor.walk(self, v, get_children=ApiObject._get_children)
  def walkabout(self, v: genericvisitor.Visitor['ApiObject']) -> None:
    """See #genericvisitor.walkabout"""
    genericvisitor.walkabout(self, v, get_children=ApiObject._get_children)

@dataclasses.dataclass
class Data(ApiObject):
  """
  Represents a variable assignment (e.g. for global variables (often used as constants) or class members).
  """

  #: The datatype associated with the assignment as code.
  datatype: t.Optional[str] = None

  #: The value of the variable as code.
  value: t.Optional[str] = None


@dataclasses.dataclass
class Function(ApiObject):
  """
  Represents a function definition. This can be in a #Module for plain functions or in a #Class for methods.
  The #decorations need to be introspected to understand if the function has a special purpose (e.g. is it a
  `@property`, `@classmethod` or `@staticmethod`?).
  """

  #: A list of modifiers used in the function definition. For example, the only valid modified in
  #: Python is "async".
  modifiers: t.Optional[t.List[str]]

  #: A list of the function arguments.
  args: t.List[Argument]

  #: The return type of the function as a code string.
  return_type: t.Optional[str]

  #: A list of decorations used on the function.
  decorations: t.Optional[t.List[Decoration]]


class HasMembers(ApiObject):
  """
  Base class for API objects that can have members, e.g. #Class and #Module.
  """

  #: The members of the API object.
  members: t.Sequence[ApiObject]

  def sync_hierarchy(self, parent: t.Optional['HasMembers'] = None) -> None:
    self.parent = parent
    for member in self.members:
      member.sync_hierarchy(self)


@dataclasses.dataclass
class Class(HasMembers):
  """
  Represents a class definition.
  """

  #: The metaclass used in the class definition as a code string.
  metaclass: t.Optional[str]

  #: The list of base classes as code strings.
  bases: t.Optional[t.List[str]]

  #: A list of decorations used in the class definition.
  decorations: t.Optional[t.List[Decoration]]

  #: A list of the classes members. #Function#s in a class are to be considered instance methods of
  #: that class unless some information about the #Function indicates otherwise.
  members: t.List['_MemberType']


@dataclasses.dataclass
class Module(HasMembers):
  """
  Represents a module, basically a named container for code/API objects. Modules may be nested in other modules.
  Be aware that for historical reasons, some loaders lile #docspec_python by default do not return nested modules,
  even if nesting would be appropriate (and instead the #Module.name simply contains the fully qualified name).
  """

  #: A list of module members.
  members: t.List['_ModuleMemberType']


_MemberType = te.Annotated[
  t.Union[Data, Function, Class],
  A.unionclass({ 'data': Data, 'function': Function, 'class': Class }, style=A.unionclass.Style.flat)]


_ModuleMemberType = te.Annotated[
  t.Union[Data, Function, Class, Module],
  A.unionclass({ 'data': Data, 'function': Function, 'class': Class, 'module': Module }, style=A.unionclass.Style.flat)]


def load_module(
  source: t.Union[str, t.TextIO, t.Dict[str, t.Any]],
  filename: t.Optional[str] = None,
  loader: t.Callable[[t.IO[str]], t.Any] = json.load,
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
    if source == '-':
      return load_module(sys.stdin, source, loader)
    with io.open(source, encoding='utf-8') as fp:
      return load_module(fp, source, loader)
  elif hasattr(source, 'read'):
    # we ar sure the type is "IO" since the source has a read attribute.
    source = loader(source) # type: ignore[arg-type]

  module = databind.json.load(source, Module, filename=filename)
  module.sync_hierarchy()
  return module


def load_modules(
  source: t.Union[str, t.TextIO, t.Iterable[t.Any]],
  filename: t.Optional[str] = None,
  loader: t.Callable[[t.IO[str]], t.Any] = json.load,
) -> t.Iterable[Module]:
  """
  Loads a stream of modules from the specified *source*. Similar to
  #load_module(), the *source* can be a filename, file-like object or a
  list of plain structured data to deserialize from.
  """

  filename = filename or getattr(source, 'name', None)

  if isinstance(source, str):
    with io.open(source, encoding='utf-8') as fp:
      yield from load_modules(fp, source, loader)
    return
  elif hasattr(source, 'read'):
    source = (loader(io.StringIO(line)) for line in t.cast(t.IO[str], source))

  for data in source:
    module = databind.json.load(data, Module, filename=filename)
    module.sync_hierarchy()
    yield module


@t.overload
def dump_module(
  module: Module,
  target: t.Union[str, t.IO[str]],
  dumper: t.Callable[[t.Any, t.IO[str]], None] = json.dump
) -> None: ...


@t.overload
def dump_module(
  module: Module,
  target: None = None,
  dumper: t.Callable[[t.Any, t.IO[str]], None] = json.dump
) -> t.Dict[str, t.Any]: ...


def dump_module(
  module: Module,
  target: t.Optional[t.Union[str, t.IO[str]]] = None,
  dumper: t.Callable[[t.Any, t.IO[str]], None] = json.dump
) -> t.Optional[t.Dict[str, t.Any]]:
  """
  Dumps a module to the specified target or returns it as plain structured data.
  """

  if isinstance(target, str):
    with io.open(target, 'w', encoding='utf-8') as fp:
      dump_module(module, fp, dumper)
    return None

  data = databind.json.dump(module, Module)
  if target:
    dumper(data, target)
    target.write('\n')
    return None
  else:
    return t.cast(t.Dict[str, t.Any], data)


def filter_visit(
  objects: t.List[ApiObject],
  predicate: t.Callable[[ApiObject], bool],
  order: str = 'pre',
) -> t.List[ApiObject]:
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
    current = objects[index - offset]
    if order == 'pre':
      if not predicate(current):
        del objects[index - offset]
        offset += 1
        continue
    if isinstance(current, HasMembers):
      current.members = filter_visit(list(current.members), predicate, order)
    if order == 'post':
      if not predicate(current):
        del objects[index - offset]
        offset += 1

  return objects


def visit(
  objects: t.List[ApiObject],
  func: t.Callable[[ApiObject], t.Any],
  order: str = 'pre',
) -> None:
  """
  Visits all *objects*, applying *func* in the specified *order*.
  """

  filter_visit(objects, (lambda obj: func(obj) or True), order)


@deprecated.deprecated(
  version='1.1.0',
  reason='#docspec.ReverseMap is deprecated and will be removed in a future version, use #ApiObject.parent '
         'and #ApiObject.path instead')
class ReverseMap:
  """
  Reverse map for finding the parent of an #ApiObject.

  @deprecated 1.1.0 -- Use #ApiObject.parent and #ApiObject.path instead of #get_parent() and #path().
  """

  def __init__(self, modules: t.List[Module]) -> None:
    pass  # don't actually need the modules since 1.1.0

  def get_parent(self, obj: ApiObject) -> t.Optional[ApiObject]:
    return obj.parent

  def path(self, obj: ApiObject) -> t.List[ApiObject]:
    return obj.path


def get_member(obj: ApiObject, name: str) -> t.Optional[ApiObject]:
  """
  Generic function to retrieve a member from an API object. This will always return #None for
  objects that don't support members (eg. #Function and #Data).
  """

  if isinstance(obj, HasMembers):
    for member in obj.members:
      if member.name == name:
        assert isinstance(member, ApiObject), (name, obj, member)
        return member

  return None

# visitors

class FilterVisitor(genericvisitor.Visitor[ApiObject]):
  """
  Visits *objects* applying the *predicate*. 
  
  If the predicate returrns #False, the object will be removed from it's containing list.
  """
  
  def __init__(self, predicate: t.Callable[[ApiObject], bool]):
    self.predicate = predicate

  def unknown_visit(self, ob: ApiObject) -> None:
    self.apply_predicate(ob)
  
  def unknown_departure(self, ob: ApiObject) -> None:
    pass
  
  def apply_predicate(self, ob: ApiObject) -> None:
    if not self.predicate(ob):
      parent = ob.parent
      if parent is None:
        raise RuntimeError(f'cannot remove root module, "{ob.full_name}", from the system.')
      name = ob.name
      assert isinstance(parent, HasMembers)
      assert isinstance(ob, (Data, Function, Class, Module))
      del parent.members[parent.members.index(ob)]
      assert get_member(parent, name) is None

class PrintVisitor(genericvisitor.Visitor[ApiObject]):
  """
  Visit objects and print each object with the defined format string. 

  Available substitutions are: 
    - "{obj_type}" (colored)
    - "{obj_name}"
    - "{obj_docstring}"
    - "{obj_lineno}"
    - "{obj_filename}"

  The default format string is: ":{obj_lineno} - {obj_type}: {obj_name}"
  """

  _COLOR_MAP = {
    Module: 'magenta',
    Class: 'cyan',
    Function: 'yellow',
    Data: 'blue',
  }
      
  def __init__(self, formatstr: str = ":{obj_lineno} - {obj_type}: {obj_name}", 
               colorize: bool = True):
        self.formatstr = formatstr
        self.colorize = colorize

  def unknown_visit(self, ob: ApiObject) -> None:
    depth = len(ob.path)-1
    tokens = dict(
      obj_type = colored(type(ob).__name__, self._COLOR_MAP.get(type(ob))) if self.colorize else type(ob).__name__,
      obj_name = ob.name,
      obj_docstring = ob.docstring or "",
      obj_lineno = str(ob.location.lineno) if ob.location else 0,
      obj_filename = ob.location.filename or '' if ob.location else '',
      )
    print('| ' * depth + self.formatstr.format(**tokens))
  
  def unknown_departure(self, ob: ApiObject) -> None:
    pass
