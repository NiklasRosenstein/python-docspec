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

from __future__ import annotations

import ast
import dataclasses
import logging
import os
import re
import sys
import textwrap
import typing as t
from io import StringIO

import blib2to3.pgen2.parse
from black.parsing import lib2to3_parse
from blib2to3.pgen2 import token
from blib2to3.pygram import python_symbols as syms
from blib2to3.pytree import NL, Context, Leaf, Node, type_repr
from docspec import (
    Argument,
    Class,
    Decoration,
    Docstring,
    Function,
    Indirection,
    Location,
    Module,
    Variable,
    _ModuleMembers,
)
from nr.util.iter import SequenceWalker

#: Logger for debugging. Slap it in when and where needed.
#:
#: Note to self and others, you can get debug log output with something like
#:
#:    do
#:      name: "debug-logging"
#:      closure: {
#:        precedes "copy-files"
#:      }
#:      action: {
#:        logging.getLogger("").setLevel(logging.DEBUG)
#:      }
#:
#: in your `build.novella` file. Be warned, it's a _lot_ of output, and lags the
#: build out considerably.
#:
_LOG = logging.getLogger(__name__)


class ParseError(blib2to3.pgen2.parse.ParseError):  # type: ignore[misc]  # Cannot subclass "ParseError" (has type "Any")  # noqa: E501
    """Extends `blib2to3.pgen2.parse.ParseError` to add a `filename` attribute."""

    msg: t.Text
    type: t.Optional[int]
    value: t.Optional[t.Text]
    context: Context
    filename: t.Text

    def __init__(
        self, msg: t.Text, type: t.Optional[int], value: t.Optional[t.Text], context: Context, filename: t.Text
    ) -> None:
        Exception.__init__(
            self, "%s: type=%r, value=%r, context=%r, filename=%r" % (msg, type, value, context, filename)
        )
        self.msg = msg
        self.type = type
        self.value = value
        self.context = context
        self.filename = filename


def dedent_docstring(s: str) -> str:
    lines = s.split("\n")
    lines[0] = lines[0].strip()
    lines[1:] = textwrap.dedent("\n".join(lines[1:])).split("\n")
    return "\n".join(lines).strip()


T = t.TypeVar("T")
V = t.TypeVar("V")


@t.overload
def find(predicate: t.Callable[[T], t.Any], iterable: t.Iterable[T], as_type: None = None) -> T | None:
    ...


@t.overload
def find(predicate: t.Callable[[T], t.Any], iterable: t.Iterable[T], as_type: type[V]) -> V | None:
    ...


@t.overload
def find(predicate: None, iterable: t.Iterable[T], as_type: type[V]) -> V | None:
    ...


def find(
    predicate: t.Callable[[T], t.Any] | None, iterable: t.Iterable[T], as_type: type[V] | None = None
) -> T | V | None:
    """Basic find function, plus the ability to add an `as_type` argument and
    receive a typed result (or raise `TypeError`).

    As you might expect, this is really only to make typing easier.
    """

    if predicate is None and as_type is not None:
        expect = as_type
        predicate = lambda x: isinstance(x, expect)  # noqa: E731
    assert predicate is not None

    for item in iterable:
        if predicate(item):
            if (as_type is not None) and (not isinstance(item, as_type)):
                raise TypeError(
                    "expected predicate to only match type {}, matched {!r}".format(
                        as_type,
                        item,
                    )
                )
            return item
    return None


@t.overload
def get(predicate: t.Callable[[T], object], iterable: t.Iterable[T], as_type: None = None) -> T:
    ...


@t.overload
def get(predicate: t.Callable[[T], object], iterable: t.Iterable[T], as_type: type[V]) -> V:
    ...


def get(predicate: t.Callable[[T], object], iterable: t.Iterable[T], as_type: type[V] | None = None) -> T | V:
    """Like `find`, but raises `ValueError` if `predicate` does not match. Assumes
    that `None` means "no match", so don't try to use it to get `None` values in
    `iterable`.
    """

    found = find(predicate, iterable, as_type)
    if found is None:
        raise ValueError("item not found for predicate {!r} in iterable {!r}".format(predicate, iterable))

    return found


def get_type_name(nl: NL) -> str:
    """Get the "type name" for a `blib2to3.pytree.NL`, which is a `Node` or
    `Leaf`. For display / debugging purposes.
    """
    if isinstance(nl, Node):
        return str(type_repr(nl.type))
    return str(token.tok_name.get(nl.type, nl.type))


def pprint_nl(nl: NL, file: t.IO[str] = sys.stdout, indent: int = 4, _depth: int = 0) -> None:
    """Pretty-print a `blib2to3.pytree.NL` over a bunch of lines, with indents,
    to make it easier to read. Display / debugging use.
    """
    assert nl.type is not None

    indent_s = " " * indent * _depth

    if nl.children:
        print(
            "{indent_s}{class_name}({type_name}, [".format(
                indent_s=indent_s,
                class_name=nl.__class__.__name__,
                type_name=get_type_name(nl),
            ),
            file=file,
        )
        for child in nl.children:
            pprint_nl(child, file=file, _depth=_depth + 1)
        print("{indent_s}])".format(indent_s=indent_s), file=file)
    else:
        print(
            "{indent_s}{class_name}({type_name}, [])".format(
                indent_s=indent_s,
                class_name=nl.__class__.__name__,
                type_name=get_type_name(nl),
            ),
            file=file,
        )


def pformat_nl(nl: NL) -> str:
    """Same as `pprint_nl`, but writes to a `str`."""
    sio = StringIO()
    pprint_nl(nl, file=sio)
    return sio.getvalue()


def get_value(node: NL) -> str:
    if isinstance(node, Leaf):
        return t.cast(str, node.value)
    raise TypeError("expected node to have a `value` attribute (be a Leaf), given {!r}".format(node))


@dataclasses.dataclass
class ParserOptions:
    # NOTE (@nrser) This is no longer used. It was passed to
    #   `lib2to3.refactor.RefactoringTool`, but that's been swapped out for
    #   `black.parsing.lib2to3_parse`, which does not take the same options.
    #
    #   It looks like it supported Python 2.x code, and I don't see anything
    #   before 3.3 in `black.mode.TargetVersion`, so 2.x might be completely off
    #   the table when using the Black parser.
    print_function: bool = True
    treat_singleline_comment_blocks_as_docstrings: bool = False


class Parser:
    def __init__(self, options: t.Optional[ParserOptions] = None) -> None:
        self.options = options or ParserOptions()

    def parse_to_ast(self, code: str, filename: str) -> NL:
        """
        Parses the string *code* to an AST with #lib2to3.
        """

        try:
            # NOTE (@NiklasRosenstein): Adding newline at the end, a ParseError
            #   could be raised without a trailing newline (tested in CPython 3.6
            #   and 3.7).
            return lib2to3_parse(code + "\n")
        except ParseError as exc:
            raise ParseError(exc.msg, exc.type, exc.value, exc.context, filename)

    def parse(self, ast: NL, filename: str, module_name: str | None = None) -> Module:
        self.filename = filename  # pylint: disable=attribute-defined-outside-init

        if module_name is None:
            module_name = os.path.basename(filename)
            module_name = os.path.splitext(module_name)[0]
            if module_name == "__init__":
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

    def parse_declaration(
        self, parent: NL, node: NL, decorations: t.Optional[list[Decoration]] = None
    ) -> t.Union[None, _ModuleMembers, t.List[_ModuleMembers]]:
        if node.type == syms.simple_stmt:
            assert not decorations
            stmt = node.children[0]
            if stmt.type in (
                syms.import_stmt,
                syms.import_name,
                syms.import_from,
                syms.import_as_names,
                syms.import_as_name,
            ):
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

    def _split_statement(self, stmt: Node) -> tuple[list[NL], list[NL], list[NL]]:
        """
        Parses a statement node into three lists, consisting of the leaf nodes
        that are the name(s), annotation and value of the expression. The value
        list will be empty if this is not an assignment statement (but for example
        a plain expression).
        """

        def _parse(
            stack: list[tuple[str, list[NL]]], current: tuple[str, list[NL]], stmt: Node
        ) -> list[tuple[str, list[NL]]]:
            for child in stmt.children:
                if not isinstance(child, Node) and child.value == "=":
                    stack.append(current)
                    current = ("value", [])
                elif not isinstance(child, Node) and child.value == ":":
                    stack.append(current)
                    current = ("annotation", [])
                elif isinstance(child, Node) and child.type == getattr(syms, "annassign", None):  # >= 3.6
                    _parse(stack, current, child)
                else:
                    current[1].append(child)
            stack.append(current)
            return stack

        result: dict[str, list[NL]] = dict(_parse([], ("names", []), stmt))
        return result.get("names", []), result.get("annotation", []), result.get("value", [])

    def parse_import(self, parent: NL, node: Node) -> t.Iterable[Indirection]:
        def _single_import_to_indirection(node: t.Union[Node, Leaf]) -> Indirection:
            if node.type == syms.dotted_as_name:  # example: urllib.request as r
                target = self.name_to_string(node.children[0])
                name = self.name_to_string(node.children[2])
                return Indirection(self.location_from(node), name, None, target)
            elif node.type == syms.dotted_name:  # example os.path
                name = self.name_to_string(node)
                return Indirection(self.location_from(node), name.split(".")[-1], None, name)
            elif isinstance(node, Leaf):
                return Indirection(self.location_from(node), node.value, None, node.value)
            else:
                raise RuntimeError(f"cannot handle {node!r}")

        def _from_import_to_indirection(prefix: str, node: t.Union[Node, Leaf]) -> Indirection:
            if node.type == syms.import_as_name:  # example: Widget as W
                target = self.name_to_string(node.children[0])
                name = self.name_to_string(node.children[2])
                return Indirection(self.location_from(node), name, None, prefix + "." + target)
            elif isinstance(node, Leaf):  # example: Widget
                name = self.name_to_string(node)
                if not prefix.endswith("."):
                    prefix += "."
                return Indirection(self.location_from(node), name, None, prefix + name)
            else:
                raise RuntimeError(f"cannot handle {node!r}")

        if node.type == syms.import_name:  # example: import ...
            subject_node = node.children[1]
            if subject_node.type == syms.dotted_as_names:
                yield from (_single_import_to_indirection(n) for n in subject_node.children if n.type != token.COMMA)
            else:
                yield _single_import_to_indirection(subject_node)

        elif node.type == syms.import_from:  # example: from xyz import ...
            index = next(
                i
                for i, n in enumerate(node.children)
                if isinstance(n, Leaf) and n.type == token.NAME and n.value == "import"
            )
            name = "".join(self.name_to_string(x) for x in node.children[1:index])
            subject_node = node.children[index + 1]
            if subject_node.type == token.LPAR:
                subject_node = node.children[index + 2]
            if subject_node.type == syms.import_as_names:
                yield from (
                    _from_import_to_indirection(name, n)
                    for n in subject_node.children
                    if n.type not in (token.LPAR, token.RPAR, token.COMMA)
                )
            else:
                yield _from_import_to_indirection(name, subject_node)

        else:
            raise RuntimeError(f"dont know how to deal with {node!r}")

    def parse_statement(self, parent: Node, stmt: Node) -> t.Optional[Variable]:
        names, annotation, value = self._split_statement(stmt)
        data: t.Optional[Variable] = None
        if value or annotation:
            docstring = self.get_statement_docstring(stmt)
            expr = self.nodes_to_string(value) if value else None
            annotation_as_string = self.nodes_to_string(annotation) if annotation else None
            assert names and len(names) == 1, (stmt, names)

            # NOTE (@NiklasRosenstein): `names` here may be a Leaf(NAME) node if we only got a
            #   single variable on the left, or a Node(testlist_star_expr) if the left operand
            #   is a more complex tuple- or range-unpacking.
            #
            #   We don't support multiple assignments in Docspec as we cannot tell how an associated
            #   docstring should be assigned to each of the resulting Variable()s, nor how the right
            #   side of the expression should be distributed among them.
            if names[0].type != token.NAME:
                return None

            # The parent node probably ends with a Leaf(NEWLINE), which will have, as its prefix, the
            # comment on the remainder of the line. Any docstring we found before or after the declaration
            # however takes precedence.
            if not docstring:
                docstring = self.prepare_docstring(parent.children[-1].prefix, parent.children[-1])

            name = self.nodes_to_string(names)
            data = Variable(
                name=name,
                location=self.location_from(stmt),
                docstring=docstring,
                datatype=annotation_as_string,
                value=expr,
            )

        return data

    def parse_decorator(self, node: Node) -> Decoration:
        assert get_value(node.children[0]) == "@"

        # NOTE (@nrser)I have no idea why `blib2to3` parses some decorators with a 'power'
        #   node (which _seems_ refer to the exponent operator `**`), but it
        #   does.
        #
        #   The hint I eventually found was:
        #
        #   https://github.com/psf/black/blob/b0d1fba7ac3be53c71fb0d3211d911e629f8aecb/src/black/nodes.py#L657
        #
        #   Anyways, this works around that curiosity.
        if node.children[1].type == syms.power:
            name = self.name_to_string(node.children[1].children[0])
            call_expr = self.nodes_to_string(node.children[1].children[1:]).strip()

        else:
            name = self.name_to_string(node.children[1])
            call_expr = self.nodes_to_string(node.children[2:]).strip()

        return Decoration(location=self.location_from(node), name=name, args=call_expr or None)

    def parse_funcdef(
        self, parent: Node, node: Node, is_async: bool, decorations: t.Optional[list[Decoration]]
    ) -> Function:
        parameters = get(lambda x: x.type == syms.parameters, node.children, as_type=Node)
        body = find(lambda x: x.type == syms.suite, node.children, as_type=Node) or get(
            lambda x: x.type == syms.simple_stmt, node.children, as_type=Node
        )

        name = get_value(node.children[1])
        docstring = self.get_docstring_from_first_node(body)
        args = self.parse_parameters(parameters)
        return_ = self.get_return_annotation(node)
        decorations = decorations or []

        return Function(
            name=name,
            location=self.location_from(node),
            docstring=docstring,
            modifiers=["async"] if is_async else None,
            args=args,
            return_type=return_,
            decorations=decorations,
        )

    def parse_argument(
        self,
        node: t.Optional[NL],
        argtype: Argument.Type,
        scanner: SequenceWalker[NL],
    ) -> Argument:
        """
        Parses an argument from the AST. *node* must be the current node at
        the current position of the *scanner*. The scanner is used to extract
        the optional default argument value that follows the *node*.
        """

        def parse_annotated_name(node: NL) -> tuple[str, t.Optional[str]]:
            if node.type in (syms.tname, syms.tname_star):
                scanner = SequenceWalker(node.children)
                name = get_value(scanner.current)
                node = scanner.next()
                assert node.type == token.COLON, node.parent
                node = scanner.next()
                annotation = self.nodes_to_string([node])
            elif node:
                name = get_value(node)
                annotation = None
            else:
                raise RuntimeError("unexpected node: {!r}".format(node))
            return (name, annotation)

        assert node is not None
        location = self.location_from(node)
        name, annotation = parse_annotated_name(node)
        assert name not in "/*", repr(node)

        node = scanner.advance()
        default = None
        if node and node.type == token.EQUAL:
            node = scanner.advance()
            assert node is not None
            default = self.nodes_to_string([node])
            scanner.advance()

        return Argument(
            location=location,
            name=name,
            type=argtype,
            datatype=annotation,
            default_value=default,
        )

    def parse_parameters(self, parameters: Node) -> list[Argument]:
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
                    result.append(
                        Argument(
                            location=self.location_from(parameters.children[1]),
                            name=get_value(parameters.children[1]),
                            type=Argument.Type.POSITIONAL,
                            decorations=None,
                            datatype=None,
                            default_value=None,
                        )
                    )
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
                # There may not be another token after the '/' -- seems like it totally
                # works to define a function like
                #
                #   def f(x, y, /):
                #     ...
                #
                node = index.advance()
                if node is not None and node.type == token.COMMA:
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
                argtype = Argument.Type.KEYWORD_ONLY
                index.advance()

            else:
                result.append(self.parse_argument(node, argtype, index))
                index.advance()

        return result

    def parse_classdef_arglist(self, classargs: NL) -> tuple[str | None, list[str]]:
        metaclass = None
        bases = []
        for child in classargs.children[::2]:
            if child.type == syms.argument:
                key, value = child.children[0].value, self.nodes_to_string(child.children[2:])
                if key == "metaclass":
                    metaclass = value
                else:
                    # TODO @NiklasRosenstein: handle metaclass arguments
                    pass
            else:
                bases.append(str(child))
        return metaclass, bases

    def parse_classdef_rawargs(self, classdef: NL) -> tuple[str | None, list[str]]:
        metaclass = None
        bases = []
        index = SequenceWalker(classdef.children, 2)
        if index.current.type == token.LPAR:
            index.next()
            while index.current.type != token.RPAR:
                if index.current.type == syms.argument:
                    key = index.current.children[0].value
                    value = str(index.current.children[2])
                    if key == "metaclass":
                        metaclass = value
                    else:
                        # TODO @NiklasRosenstein: handle metaclass arguments
                        pass
                else:
                    bases.append(str(index.current))
                index.next()
        return metaclass, bases

    def parse_classdef(self, parent: Node, node: Node, decorations: t.Optional[list[Decoration]]) -> Class:
        name = get_value(node.children[1])
        bases: list[str] = []
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
            members=[],
        )

        for child in suite.children if suite else []:
            if isinstance(child, Node):
                members = self.parse_declaration(class_, child) or []
                if not isinstance(members, list):
                    members = [members]
                for member in members:
                    assert not isinstance(member, Module)
                    if metaclass is None and isinstance(member, Variable) and member.name == "__metaclass__":
                        metaclass = member.value
                    elif member:
                        class_.members.append(member)

        class_.metaclass = metaclass
        return class_

    def location_from(self, node: NL) -> Location:
        # NOTE (@nrser) `blib2to3.pytree.Base.get_lineno` may return `None`, but
        #   `Location` expects an `int`, so not sure exactly what to do here... for
        #   the moment just return a bogus value of -1
        lineno = node.get_lineno()
        if lineno is None:
            lineno = -1
        return Location(self.filename, lineno)

    def get_return_annotation(self, node: Node) -> t.Optional[str]:
        rarrow = find(lambda x: x.type == token.RARROW, node.children)
        if rarrow:
            assert rarrow.next_sibling  # satisfy type checker
            return self.nodes_to_string([rarrow.next_sibling])
        return None

    def get_most_recent_prefix(self, node: NL) -> str:
        if node.prefix:
            return t.cast(str, node.prefix)
        while not node.prev_sibling and not node.prefix:
            if not node.parent:
                return ""
            node = node.parent
        if node.prefix:
            return t.cast(str, node.prefix)
        while isinstance(node.prev_sibling, Node) and node.prev_sibling.children:
            node = node.prev_sibling.children[-1]
        return t.cast(str, node.prefix)

    def get_docstring_from_first_node(self, parent: NL, module_level: bool = False) -> t.Optional[Docstring]:
        """
        This method retrieves the docstring for the block node *parent*. The
        node either declares a class or function.
        """

        assert parent is not None
        node = find(None, parent.children, as_type=Node)

        if node and node.type == syms.simple_stmt and node.children[0].type == token.STRING:
            return self.prepare_docstring(get_value(node.children[0]), parent)

        if not node and not module_level:
            return None

        if self.options.treat_singleline_comment_blocks_as_docstrings:
            docstring, doc_type = self.get_hashtag_docstring_from_prefix(node or parent)
            if doc_type == "block":
                return docstring

        return None

    def get_statement_docstring(self, node: NL) -> t.Optional[Docstring]:
        prefix = self.get_most_recent_prefix(node)
        match = re.match(r"\s*", prefix[::-1])
        assert match is not None
        ws = match.group(0)
        if ws.count("\n") == 1:
            docstring, doc_type = self.get_hashtag_docstring_from_prefix(node)
            if doc_type == "statement":
                return docstring
        # Look for the next string literal instead.
        curr: t.Optional[NL] = node
        while curr and curr.type != syms.simple_stmt:
            curr = curr.parent
        if curr and curr.next_sibling and curr.next_sibling.type == syms.simple_stmt:
            string_literal = curr.next_sibling.children[0]
            if string_literal.type == token.STRING:
                assert isinstance(string_literal, Leaf)
                return self.prepare_docstring(string_literal.value, string_literal)
        return None

    def get_hashtag_docstring_from_prefix(
        self,
        node: NL,
    ) -> t.Tuple[t.Optional[Docstring], t.Optional[str]]:
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
        for line in reversed(prefix.split("\n")):
            line = line.strip()
            if lines and not line.startswith("#"):
                break
            if doc_type is None and line.strip().startswith("#:"):
                doc_type = "statement"
            elif doc_type is None and line.strip().startswith("#"):
                doc_type = "block"
            if lines or line:
                lines.append(line)

        return self.prepare_docstring("\n".join(reversed(lines)), node), doc_type

    def prepare_docstring(self, s: str, node_for_location: NL) -> t.Optional[Docstring]:
        location = self.location_from(node_for_location)
        s = s.strip()
        if s.startswith("#"):
            location.lineno -= s.count("\n") + 2
            lines = []
            initial_indent: t.Optional[int] = None
            for line in s.split("\n"):
                if line.startswith("#:"):
                    line = line[2:]
                elif line.startswith("#"):
                    line = line[1:]
                else:
                    assert False, repr(line)
                if initial_indent is None:
                    initial_indent = len(line) - len(line.lstrip())
                # Strip up to initial_indent whitespace from the line.
                new_line = line.lstrip()
                new_line = " " * max(0, len(line) - len(new_line) - initial_indent) + new_line
                lines.append(new_line.rstrip())
            return Docstring(location, "\n".join(lines).strip())
        if s:
            s = ast.literal_eval(s)
            return Docstring(location, dedent_docstring(s).strip())
        return None

    def nodes_to_string(self, nodes: list[NL]) -> str:
        """
        Converts a list of AST nodes to a string.
        """

        def generator(nodes: t.List[NL], skip_prefix: bool = True) -> t.Iterable[str]:
            for i, node in enumerate(nodes):
                if not skip_prefix or i != 0:
                    yield node.prefix
                if isinstance(node, Node):
                    yield from generator(node.children, True)
                else:
                    yield node.value

        return "".join(generator(nodes))

    def name_to_string(self, node: NL) -> str:
        if node.type == syms.dotted_name:
            return "".join(get_value(x) for x in node.children)
        else:
            return get_value(node)
