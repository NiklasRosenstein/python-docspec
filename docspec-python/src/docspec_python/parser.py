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


import os
import re
import textwrap
import typing as t

from docspec import (
  Argument,
  Class,
  Data,
  Decoration,
  Function,
  Location,
  Module)
from lib2to3.refactor import RefactoringTool  # type: ignore
from lib2to3.pgen2 import token
from lib2to3.pgen2.parse import ParseError
from lib2to3.pygram import python_symbols as syms
from lib2to3.pytree import Leaf, Node
from nr.databind.core import Field, Struct  # type: ignore

_REVERSE_SYMS = {v: k for k, v in vars(syms).items() if isinstance(v, int)}
_REVERSE_TOKEN = {v: k for k, v in vars(token).items() if isinstance(v, int)}


def dedent_docstring(s):
  lines = s.split('\n')
  lines[0] = lines[0].strip()
  lines[1:] = textwrap.dedent('\n'.join(lines[1:])).split('\n')
  return '\n'.join(lines).strip()


def find(predicate, iterable):
  for item in iterable:
    if predicate(item):
      return item
  return None


class ParserOptions(Struct):
  print_function = Field(bool, default=True)
  treat_singleline_comment_blocks_as_docstrings = Field(bool, default=False)


class Parser:

  def __init__(self, options: ParserOptions = None) -> None:
    self.options = options or ParserOptions()

  def parse_to_ast(self, code, filename):
    """
    Parses the string *code* to an AST with #lib2to3.
    """

    options = {'print_function': self.options.print_function}

    try:
      # NOTE (@NiklasRosenstein): Adding newline at the end, a ParseError
      #   could be raised without a trailing newline (tested in CPython 3.6
      #   and 3.7).
      return RefactoringTool([], options).refactor_string(code + '\n', filename)
    except ParseError as exc:
      raise ParseError(exc.msg, exc.type, exc.value, tuple(exc.context) + (filename,))

  def parse(self, ast, filename, module_name=None):
    self.filename = filename  # pylint: disable=attribute-defined-outside-init

    if module_name is None:
      module_name = os.path.basename(filename)
      module_name = os.path.splitext(module_name)[0]
      if module_name == '__init__':
        module_name = os.path.basename(os.path.dirname(filename))

    docstring = self.get_docstring_from_first_node(ast, module_level=True)
    module = Module(
      name=module_name,
      location=self.location_from(ast),
      docstring=docstring,
      members=[],
    )

    for node in ast.children:
      member = self.parse_declaration(module, node)
      if member:
        module.members.append(member)

    return module

  def parse_declaration(self, parent, node, decorations=None):
    if node.type == syms.simple_stmt:
      assert not decorations
      stmt = node.children[0]
      if stmt.type in (syms.import_name, syms.import_from):
        # TODO @NiklasRosenstein handle import statements?
        pass
      elif stmt.type == syms.expr_stmt:
        return self.parse_statement(parent, stmt)
    elif node.type == syms.funcdef:
      return self.parse_funcdef(parent, node, False, decorations)
    elif node.type == syms.classdef:
      return self.parse_classdef(parent, node, decorations)
    elif node.type in (syms.async_stmt, syms.async_funcdef):
      child = node.children[1]
      if child.type == syms.funcdef:
        return self.parse_funcdef(parent, child, True, decorations)
    elif node.type == syms.decorated:
      assert len(node.children) == 2
      decorations = []
      if node.children[0].type == syms.decorator:
        decorator_nodes = [node.children[0]]
      elif node.children[0].type == syms.decorators:
        decorator_nodes = node.children[0].children
      else:
        assert False, node.children[0].type
      for child in decorator_nodes:
        assert child.type == syms.decorator, child.type
        decorations.append(self.parse_decorator(child))
      return self.parse_declaration(parent, node.children[1], decorations)
    return None

  def _split_statement(self, stmt):
    """
    Parses a statement node into three lists, consisting of the leaf nodes
    that are the name(s), annotation and value of the expression. The value
    list will be empty if this is not an assignment statement (but for example
    a plain expression).
    """

    def _parse(stack, current, stmt):
      for child in stmt.children:
        if not isinstance(child, Node) and child.value == '=':
          stack.append(current)
          current = ('value', [])
        elif not isinstance(child, Node) and child.value == ':':
          stack.append(current)
          current = ('annotation', [])
        elif isinstance(child, Node) and child.type == getattr(syms, 'annassign', None):  # >= 3.6
          _parse(stack, current, child)
        else:
          current[1].append(child)
      stack.append(current)
      return stack

    result = dict(_parse([], ('names', []), stmt))
    return result.get('names', []), result.get('annotation', []), result.get('value', [])

  def parse_statement(self, parent, stmt):
    names, annotation, value = self._split_statement(stmt)
    if value or annotation:
      docstring = self.get_statement_docstring(stmt)
      expr = self.nodes_to_string(value) if value else None
      annotation = self.nodes_to_string(annotation) if annotation else None
      assert names
      for name in names:
        name = self.nodes_to_string([name])
        data = Data(
          name=name,
          location=self.location_from(stmt),
          docstring=docstring,
          datatype=annotation,
          value=expr,
        )
      return data
    return None

  def parse_decorator(self, node):
    assert node.children[0].value == '@'
    name = self.name_to_string(node.children[1])
    call_expr = self.nodes_to_string(node.children[2:]).strip()
    return Decoration(name=name, args=call_expr or None)

  def parse_funcdef(self, parent, node, is_async, decorations):
    parameters = find(lambda x: x.type == syms.parameters, node.children)
    body = find(lambda x: x.type == syms.suite, node.children) or \
      find(lambda x: x.type == syms.simple_stmt, node.children)

    name = node.children[1].value
    docstring = self.get_docstring_from_first_node(body)
    args = self.parse_parameters(parameters)
    return_ = self.get_return_annotation(node)
    decorations = decorations or []

    return Function(
      name=name,
      location=self.location_from(node),
      docstring=docstring,
      modifiers=['async'] if is_async else None,
      args=args,
      return_type=return_,
      decorations=decorations)

  def parse_argument(self, node: t.Union[Leaf, Node], argtype: Argument.Type, scanner: 'ListScanner') -> Argument:
    """
    Parses an argument from the AST. *node* must be the current node at
    the current position of the *scanner*. The scanner is used to extract
    the optional default argument value that follows the *node*.
    """

    def parse_annotated_name(node):
      if node.type == syms.tname:
        scanner = ListScanner(node.children)
        name = scanner.current.value
        node = scanner.advance()
        assert node.type == token.COLON, node.parent
        node = scanner.advance()
        annotation = self.nodes_to_string([node])
      elif node:
        name = node.value
        annotation = None
      else:
        raise RuntimeError('unexpected node: {!r}'.format(node))
      return (name, annotation)

    name, annotation = parse_annotated_name(node)

    node = scanner.advance()
    default = None
    if node and node.type == token.EQUAL:
      node = scanner.advance()
      default = self.nodes_to_string([node])
      scanner.advance()

    return Argument(name, argtype, None, annotation, default)

  def parse_parameters(self, parameters):
    assert parameters.type == syms.parameters, parameters.type
    result = []

    arglist = find(lambda x: x.type == syms.typedargslist, parameters.children)
    if not arglist:
      # NOTE (@NiklasRosenstein): A single argument (annotated or not) does
      #   not get wrapped in a `typedargslist`, but in a single `tname`.
      tname = find(lambda x: x.type == syms.tname, parameters.children)
      if tname:
        scanner = ListScanner(parameters.children, parameters.children.index(tname))
        result.append(self.parse_argument(tname, Argument.Type.Positional, scanner))
      else:
        # This must be either ["(", ")"] or ["(", "argname", ")"].
        assert len(parameters.children) in (2, 3), parameters.children
        if len(parameters.children) == 3:
          result.append(Argument(parameters.children[1].value, Argument.Type.Positional, None, None, None))
      return result

    argtype = Argument.Type.Positional

    index = ListScanner(arglist.children)
    for node in index.safe_iter(auto_advance=False):
      node = index.current
      if node.type == token.STAR:
        node = index.advance()
        if node.type != token.COMMA:
          result.append(self.parse_argument(node, Argument.Type.PositionalRemainder, index))
        index.advance()
        argtype = Argument.Type.KeywordOnly
        continue
      elif node.type == token.DOUBLESTAR:
        node = index.advance()
        result.append(self.parse_argument(node, Argument.Type.KeywordRemainder, index))
        continue
      result.append(self.parse_argument(node, argtype, index))
      index.advance()

    return result

  def parse_classdef_arglist(self, classargs):
    metaclass = None
    bases = []
    for child in classargs.children[::2]:
      if child.type == syms.argument:
        key, value = child.children[0].value, self.nodes_to_string(child.children[2:])
        if key == 'metaclass':
          metaclass = value
        else:
          # TODO @NiklasRosenstein: handle metaclass arguments
          pass
      else:
        bases.append(str(child))
    return metaclass, bases

  def parse_classdef_rawargs(self, classdef):
    metaclass = None
    bases = []
    index = ListScanner(classdef.children, 2)
    if index.current.type == token.LPAR:
      index.advance()
      while index.current.type != token.RPAR:
        if index.current.type == syms.argument:
          key = index.current.children[0].value
          value = str(index.current.children[2])
          if key == 'metaclass':
            metaclass = value
          else:
            # TODO @NiklasRosenstein: handle metaclass arguments
            pass
        else:
          bases.append(str(index.current))
        index.advance()
    return metaclass, bases

  def parse_classdef(self, parent, node, decorations):
    name = node.children[1].value
    bases = []
    metaclass = None

    # An arglist is available if there are at least two parameters.
    # Otherwise we have to deal with parsing a raw sequence of nodes.
    classargs = find(lambda x: x.type == syms.arglist, node.children)
    if classargs:
      metaclass, bases = self.parse_classdef_arglist(classargs)
    else:
      metaclass, bases = self.parse_classdef_rawargs(node)

    suite = find(lambda x: x.type == syms.suite, node.children)
    docstring = self.get_docstring_from_first_node(suite)
    class_ = Class(
      name=name,
      location=self.location_from(node),
      docstring=docstring,
      metaclass=metaclass,
      bases=bases,
      decorations=decorations,
      members=[])

    for child in suite.children:
      if isinstance(child, Node):
        member = self.parse_declaration(class_, child)
        if metaclass is None and isinstance(member, Data) and \
            member.name == '__metaclass__':
          metaclass = member.value
        elif member:
          class_.members.append(member)

    class_.metaclass = metaclass
    return class_

  def location_from(self, node):
    return Location(self.filename, node.get_lineno())

  def get_return_annotation(self, node):
    rarrow = find(lambda x: x.type == token.RARROW, node.children)
    if rarrow:
      node = rarrow.next_sibling
      return self.nodes_to_string([node])
    return None

  def get_most_recent_prefix(self, node):
    if node.prefix:
      return node.prefix
    while not node.prev_sibling and not node.prefix:
      if not node.parent:
        return ''
      node = node.parent
    if node.prefix:
      return node.prefix
    node = node.prev_sibling
    while isinstance(node, Node) and node.children:
      node = node.children[-1]
    return node.prefix

  def get_docstring_from_first_node(self, parent, module_level=False):
    """
    This method retrieves the docstring for the block node *parent*. The
    node either declares a class or function.
    """

    node = find(lambda x: isinstance(x, Node), parent.children)
    if node and node.type == syms.simple_stmt and node.children[0].type == token.STRING:
      return self.prepare_docstring(node.children[0].value)
    if not node and not module_level:
      return None
    if self.options.treat_singleline_comment_blocks_as_docstrings:
      docstring, doc_type = self.get_hashtag_docstring_from_prefix(node or parent)
      if doc_type == 'block':
        return docstring
    return None

  def get_statement_docstring(self, node):
    prefix = self.get_most_recent_prefix(node)
    match = re.match(r'\s*', prefix[::-1])
    assert match is not None
    ws = match.group(0)
    if ws.count('\n') == 1:
      docstring, doc_type = self.get_hashtag_docstring_from_prefix(node)
      if doc_type == 'statement':
        return docstring
    # Look for the next string literal instead.
    while node and node.type != syms.simple_stmt:
      node = node.parent
    if node and node.next_sibling and node.next_sibling.type == syms.simple_stmt:
      string_literal = node.next_sibling.children[0]
      if string_literal.type == token.STRING:
        return self.prepare_docstring(string_literal.value)
    return None

  def get_hashtag_docstring_from_prefix(self, node: Node) -> t.Tuple[t.Optional[str], t.Optional[str]]:
    """
    Given a node in the AST, this method retrieves the docstring from the
    closest prefix of this node (ie. any block of single-line comments that
    precede this node).

    The function will also return the type of docstring: A docstring that
    begins with `#:` is a statement docstring, otherwise it is a block
    docstring (and only used for classes/methods).

    return: (docstring, doc_type)
    """

    prefix = self.get_most_recent_prefix(node)
    lines: t.List[str] = []
    doc_type = None
    for line in reversed(prefix.split('\n')):
      line = line.strip()
      if lines and not line.startswith('#'):
        break
      if doc_type is None and line.strip().startswith('#:'):
        doc_type = 'statement'
      elif doc_type is None and line.strip().startswith('#'):
        doc_type = 'block'
      if lines or line:
        lines.append(line)
    return self.prepare_docstring('\n'.join(reversed(lines))), doc_type

  def prepare_docstring(self, s):
    # TODO @NiklasRosenstein handle u/f prefixes of string literal?
    s = s.strip()
    if s.startswith('#'):
      lines = []
      for line in s.split('\n'):
        line = line.strip()
        if line.startswith('#:'):
          line = line[2:]
        else:
          line = line[1:]
        lines.append(line.lstrip())
      return '\n'.join(lines).strip()
    if s.startswith('"""') or s.startswith("'''"):
      return dedent_docstring(s[3:-3]).strip()
    if s.startswith('"') or s.startswith("'"):
      return dedent_docstring(s[1:-1]).strip()
    return None

  def nodes_to_string(self, nodes):
    """
    Converts a list of AST nodes to a string.
    """

    def generator(nodes: t.List[t.Union[Node, Leaf]], skip_prefix: bool = True) -> t.Iterable[str]:
      for i, node in enumerate(nodes):
        if not skip_prefix or i != 0:
          yield node.prefix
        if isinstance(node, Node):
          yield from generator(node.children, True)
        else:
          yield node.value

    return ''.join(generator(nodes))

  def name_to_string(self, node):
    if node.type == syms.dotted_name:
      return ''.join(x.value for x in node.children)
    else:
      return node.value


class ListScanner:
  """
  A helper class to navigate through a list. This is useful if you would
  usually iterate over the list by index to be able to acces the next
  element during the iteration.

  Example:

  ```py
  scanner = ListScanner(lst)
  for value in scanner.safe_iter():
    if some_condition(value):
      value = scanner.advance()
  ```
  """

  def __init__(self, lst, index=0):
    self._list = lst
    self._index = index

  def __bool__(self):
    return self._index < len(self._list)

  __nonzero__ = __bool__

  @property
  def current(self):
    """
    Returns the current list element.
    """

    return self._list[self._index]

  def can_advance(self):
    """
    Returns `True` if there is a next element in the list.
    """

    return self._index < (len(self._list) - 1)

  def advance(self, expect=False):
    """
    Advances the scanner to the next element in the list. If *expect* is set
    to `True`, an #IndexError will be raised when there is no next element.
    Otherwise, `None` will be returned.
    """

    self._index += 1
    try:
      return self.current
    except IndexError:
      if expect:
        raise
      return None

  def safe_iter(self, auto_advance=True):
    """
    A useful generator function that iterates over every element in the list.
    You may call #advance() during the iteration to retrieve the next
    element in the list within a single iteration.

    If *auto_advance* is `True` (default), the function generator will
    always advance to the next element automatically. If it is set to `False`,
    #advance() must be called manually in every iteration to ensure that
    the scanner has advanced at least to the next element, or a
    #RuntimeError will be raised.
    """

    index = self._index
    while self:
      yield self.current
      if auto_advance:
        self.advance()
      elif self._index == index:
        raise RuntimeError('next() has not been called on the ListScanner')
