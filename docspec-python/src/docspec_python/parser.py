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

"""
Note: The `docspec_python.parser` module is not public API.
"""

import dataclasses
import os
import re
import textwrap
import typing as t

from nr.util.iter import SequenceWalker

from docspec import (
  Argument,
  Class,
  Variable,
  Docstring,
  Decoration,
  Function,
  Indirection,
  Location,
  Module,
  _ModuleMembers)
from lib2to3.refactor import RefactoringTool  # type: ignore
from lib2to3.pgen2 import token
from lib2to3.pgen2.parse import ParseError
from lib2to3.pygram import python_symbols as syms
from lib2to3.pytree import Leaf, Node


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


@dataclasses.dataclass
class ParserOptions:
  print_function: bool = True
  treat_singleline_comment_blocks_as_docstrings: bool = False


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
      if isinstance(member, list):
        module.members += member
      elif member:
        module.members.append(member)

    module.sync_hierarchy()
    return module

  def parse_declaration(self, parent, node, decorations=None) -> t.Union[None, _ModuleMembers, t.List[_ModuleMembers]]:
    if node.type == syms.simple_stmt:
      assert not decorations
      stmt = node.children[0]
      if stmt.type in (syms.import_stmt, syms.import_name, syms.import_from, syms.import_as_names, syms.import_as_name):
        return list(self.parse_import(node, stmt))
      elif stmt.type == syms.expr_stmt:
        return self.parse_statement(node, stmt)
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

  def parse_import(self, parent, node: Node) -> t.Iterable[Indirection]:

    def _single_import_to_indirection(node: t.Union[Node, Leaf]) -> Indirection:
      if node.type == syms.dotted_as_name:  # example: urllib.request as r
        target = self.name_to_string(node.children[0])
        name = self.name_to_string(node.children[2])
        return Indirection(self.location_from(node),name, None, target)
      elif node.type == syms.dotted_name:  # example os.path
        name = self.name_to_string(node)
        return Indirection(self.location_from(node), name.split('.')[-1], None, name)
      elif isinstance(node, Leaf):
        return Indirection(self.location_from(node), node.value, None, node.value)
      else:
        raise RuntimeError(f'cannot handle {node!r}')

    def _from_import_to_indirection(prefix: str, node: t.Union[Node, Leaf]) -> Indirection:
      if node.type == syms.import_as_name:  # example: Widget as W
        target = self.name_to_string(node.children[0])
        name = self.name_to_string(node.children[2])
        return Indirection(self.location_from(node), name, None, prefix + '.' + target)
      elif isinstance(node, Leaf):  # example: Widget
        name = self.name_to_string(node)
        if not prefix.endswith('.'):
          prefix += '.'
        return Indirection(self.location_from(node), name, None, prefix + name)
      else:
        raise RuntimeError(f'cannot handle {node!r}')

    if node.type == syms.import_name:  # example: import ...
      subject_node = node.children[1]
      if subject_node.type == syms.dotted_as_names:
        yield from (_single_import_to_indirection(n) for n in subject_node.children if n.type != token.COMMA)
      else:
        yield _single_import_to_indirection(subject_node)

    elif node.type == syms.import_from:  # example: from xyz import ...
      index = next(i for i, n in enumerate(node.children) if isinstance(n, Leaf) and n.type == token.NAME and n.value == 'import')
      name = ''.join(self.name_to_string(x) for x in node.children[1:index])
      subject_node = node.children[index + 1]
      if subject_node.type == token.LPAR:
        subject_node = node.children[index + 2]
      if subject_node.type == syms.import_as_names:
        yield from (_from_import_to_indirection(name, n) for n in subject_node.children if n.type not in (token.LPAR, token.RPAR, token.COMMA))
      else:
        yield _from_import_to_indirection(name, subject_node)

    else:
      raise RuntimeError(f'dont know how to deal with {node!r}')

  def parse_statement(self, parent, stmt):
    names, annotation, value = self._split_statement(stmt)
    if value or annotation:
      docstring = self.get_statement_docstring(stmt)
      expr = self.nodes_to_string(value) if value else None
      annotation = self.nodes_to_string(annotation) if annotation else None
      assert names
      for name in names:
        name = self.nodes_to_string([name])
        data = Variable(
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
    return Decoration(location=self.location_from(node), name=name, args=call_expr or None)

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

  def parse_argument(self, node: t.Union[Leaf, Node, None], argtype: Argument.Type, scanner: 'SequenceWalker[Leaf | Node]') -> Argument:
    """
    Parses an argument from the AST. *node* must be the current node at
    the current position of the *scanner*. The scanner is used to extract
    the optional default argument value that follows the *node*.
    """

    def parse_annotated_name(node):
      if node.type == syms.tname:
        scanner = SequenceWalker(node.children)
        name = scanner.current.value
        node = scanner.next()
        assert node.type == token.COLON, node.parent
        node = scanner.next()
        annotation = self.nodes_to_string([node])
      elif node:
        name = node.value
        annotation = None
      else:
        raise RuntimeError('unexpected node: {!r}'.format(node))
      return (name, annotation)

    assert node is not None
    location = self.location_from(node)
    name, annotation = parse_annotated_name(node)
    assert name not in '/*', repr(node)

    node = scanner.advance()
    default = None
    if node and node.type == token.EQUAL:
      node = scanner.advance()
      default = self.nodes_to_string([node])
      scanner.advance()

    return Argument(
      location=location,
      name=name,
      type=argtype,
      datatype=annotation,
      default_value=default,
    )

  def parse_parameters(self, parameters):
    assert parameters.type == syms.parameters, parameters.type
    result: t.List[Argument] = []

    arglist = find(lambda x: x.type == syms.typedargslist, parameters.children)
    if not arglist:
      # NOTE (@NiklasRosenstein): A single argument (annotated or not) does
      #   not get wrapped in a `typedargslist`, but in a single `tname`.
      tname = find(lambda x: x.type == syms.tname, parameters.children)
      if tname:
        scanner = SequenceWalker(parameters.children, parameters.children.index(tname))
        result.append(self.parse_argument(tname, Argument.Type.POSITIONAL, scanner))
      else:
        # This must be either ["(", ")"] or ["(", "argname", ")"].
        assert len(parameters.children) in (2, 3), parameters.children
        if len(parameters.children) == 3:
          result.append(Argument(
            location=self.location_from(parameters.children[1]),
            name=parameters.children[1].value,
            type=Argument.Type.POSITIONAL,
            decorations=None,
            datatype=None,
            default_value=None,
          ))
      return result

    argtype = Argument.Type.POSITIONAL

    index = SequenceWalker(arglist.children)
    for node in index.safe_iter():
      node = index.current

      if node.type == token.SLASH:
        assert argtype == Argument.Type.POSITIONAL
        # We need to retrospectively change the argument type of previous parsed arguments to POSITIONAL_ONLY.
        for arg in result:
          assert arg.type == Argument.Type.POSITIONAL, arg
          arg.type = Argument.Type.POSITIONAL_ONLY
        node = index.next()
        if node.type == token.COMMA:
          index.advance()

      elif node.type == token.STAR:
        node = index.next()
        if node and node.type != token.COMMA:
          result.append(self.parse_argument(node, Argument.Type.POSITIONAL_REMAINDER, index))
        index.advance()
        argtype = Argument.Type.KEYWORD_ONLY

      elif node and node.type == token.DOUBLESTAR:
        node = index.next()
        result.append(self.parse_argument(node, Argument.Type.KEYWORD_REMAINDER, index))

      else:
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
    index = SequenceWalker(classdef.children, 2)
    if index.current.type == token.LPAR:
      index.next()
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
        index.next()
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
    docstring = self.get_docstring_from_first_node(suite) if suite else None
    class_ = Class(
      name=name,
      location=self.location_from(node),
      docstring=docstring,
      metaclass=metaclass,
      bases=[b.strip() for b in bases],
      decorations=decorations,
      members=[])

    for child in suite.children if suite else []:
      if isinstance(child, Node):
        members = self.parse_declaration(class_, child) or []
        if not isinstance(members, list):
          members = [members]
        for member in members:
          assert not isinstance(member, Module)
          if metaclass is None and isinstance(member, Variable) and \
              member.name == '__metaclass__':
            metaclass = member.value
          elif member:
            class_.members.append(member)

    class_.metaclass = metaclass
    return class_

  def location_from(self, node: t.Union[Node, Leaf]) -> Location:
    return Location(self.filename, node.get_lineno())

  def get_return_annotation(self, node: Node) -> t.Optional[str]:
    rarrow = find(lambda x: x.type == token.RARROW, node.children)
    if rarrow:
      node = rarrow.next_sibling
      return self.nodes_to_string([node])
    return None

  def get_most_recent_prefix(self, node) -> str:
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

  def get_docstring_from_first_node(self, parent: Node, module_level: bool = False) -> t.Optional[Docstring]:
    """
    This method retrieves the docstring for the block node *parent*. The
    node either declares a class or function.
    """

    assert parent is not None
    node = find(lambda x: isinstance(x, Node), parent.children)
    if node and node.type == syms.simple_stmt and node.children[0].type == token.STRING:
      return self.prepare_docstring(node.children[0].value, parent)
    if not node and not module_level:
      return None
    if self.options.treat_singleline_comment_blocks_as_docstrings:
      docstring, doc_type = self.get_hashtag_docstring_from_prefix(node or parent)
      if doc_type == 'block':
        return docstring
    return None

  def get_statement_docstring(self, node: Node) -> t.Optional[Docstring]:
    prefix = self.get_most_recent_prefix(node)
    match = re.match(r'\s*', prefix[::-1])
    assert match is not None
    ws = match.group(0)
    if ws.count('\n') == 1:
      docstring, doc_type = self.get_hashtag_docstring_from_prefix(node)
      if doc_type == 'statement':
        return docstring
    # Look for the next string literal instead.
    curr: t.Optional[Node] = node
    while curr and curr.type != syms.simple_stmt:
      curr = curr.parent
    if curr and curr.next_sibling and curr.next_sibling.type == syms.simple_stmt:
      string_literal = curr.next_sibling.children[0]
      if string_literal.type == token.STRING:
        assert isinstance(string_literal, Leaf)
        return self.prepare_docstring(string_literal.value, string_literal)
    return None

  def get_hashtag_docstring_from_prefix(self, node: Node) -> t.Tuple[t.Optional[Docstring], t.Optional[str]]:
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

    return self.prepare_docstring('\n'.join(reversed(lines)), node), doc_type

  def prepare_docstring(self, s: str, node_for_location: t.Union[Node, Leaf]) -> t.Optional[Docstring]:
    # TODO @NiklasRosenstein handle u/f prefixes of string literal?
    location = self.location_from(node_for_location)
    s = s.strip()
    if s.startswith('#'):
      location.lineno -= s.count('\n') + 2
      lines = []
      for line in s.split('\n'):
        line = line.strip()
        if line.startswith('#:'):
          line = line[2:]
        else:
          line = line[1:]
        lines.append(line.lstrip())
      return Docstring(location, '\n'.join(lines).strip())
    if s.startswith('"""') or s.startswith("'''"):
      return Docstring(location, dedent_docstring(s[3:-3]).strip())
    if s.startswith('"') or s.startswith("'"):
      return Docstring(location, dedent_docstring(s[1:-1]).strip())
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
