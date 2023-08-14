"""
A new parser based on the ``ast`` module, the framework ``libstatic`` and ``ast-comments``
"""
from __future__ import annotations

import ast
from functools import partial
import inspect
import platform
import sys
import typing as t
from dataclasses import dataclass
from itertools import chain

import ast_comments  # type:ignore[import]
import astor  # type:ignore[import]
import docspec
import libstatic  # type:ignore[import]
from libstatic._lib.assignment import get_stored_value  # type:ignore[import]
from libstatic._lib.shared import LocalStmtVisitor, unparse  # type:ignore[import]


class ModSpec(t.NamedTuple):
    src: str
    modname: str
    filename: str | None = None
    is_package: bool = False
    is_stub: bool = False


@dataclass
class ParserOptions:
    expand_names: bool = True
    builtins: bool = False
    dependencies: bool | int = False
    verbosity:int = 0
    # python_version:tuple[int, int]

class ParseError(Exception):
    ...

def parse_modules(modules: t.Sequence[ModSpec], options: ParserOptions | None = None) -> t.Iterator[docspec.Module]:
    options = options or ParserOptions()
    proj = libstatic.Project(builtins=options.builtins, 
                             verbosity=options.verbosity)
    initial_modules: dict[str, str] = {}  # libstatic may add the builtins module
    for src, modname, filename, is_package, is_stub in modules:
        initial_modules[modname] = src
        filename = filename or "<unknown>"
        try:
            node = ast.parse(src, filename=filename)
        except SyntaxError as e:
            raise ParseError(f'cannot parse file: {e}') from e
        try:
            proj.add_module(
                node, 
                modname, 
                is_package=is_package, 
                filename=filename
            )
        except libstatic.StaticException as e:
            raise ParseError(f'cannot add module {modname!r} to the project: {e}') from e
        
    proj.analyze_project()
    parser = Parser(proj.state, options)
    for m in proj.state.get_all_modules():
        if m.name() in initial_modules:
            # run ast-comments
            ast_comments._enrich(initial_modules[m.name()], m.node)
            yield parser.parse(m)  # type: ignore[misc]


class IVar(t.NamedTuple):
    node: ast.Attribute
    value: ast.expr | None = None
    annotation: ast.expr | None = None


class ArgSpec(t.NamedTuple):
    node: ast.arg
    type: docspec.Argument.Type
    default: ast.expr | None = None


def _iter_arguments(args: ast.arguments) -> t.Iterator[ArgSpec]:
    """
    Yields all arguments of the given ast.arguments instance.
    """
    posonlyargs = getattr(args, "posonlyargs", ())

    num_pos_args = len(posonlyargs) + len(args.args)
    defaults = args.defaults
    default_offset = num_pos_args - len(defaults)

    def get_default(index: int) -> ast.expr | None:
        assert 0 <= index < num_pos_args, index
        index -= default_offset
        return None if index < 0 else defaults[index]

    for i, arg in enumerate(posonlyargs):
        yield ArgSpec(arg, docspec.Argument.Type.POSITIONAL_ONLY, default=get_default(i))
    for i, arg in enumerate(args.args, start=len(posonlyargs)):
        yield ArgSpec(arg, docspec.Argument.Type.POSITIONAL, default=get_default(i))
    if args.vararg:
        yield ArgSpec(args.vararg, docspec.Argument.Type.POSITIONAL_REMAINDER)
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        yield ArgSpec(arg, docspec.Argument.Type.KEYWORD_ONLY, default=default)
    if args.kwarg:
        yield ArgSpec(args.kwarg, docspec.Argument.Type.KEYWORD_REMAINDER)


_string_lineno_is_end = sys.version_info < (3, 8) and platform.python_implementation() != "PyPy"
"""True iff the 'lineno' attribute of an AST string node points to the last
line in the string, rather than the first line.
"""


def _extract_docstring_linenum(node: ast.Str | ast.Constant) -> int:
    r"""
    In older CPython versions, the AST only tells us the end line
    number and we must approximate the start line number.
    This approximation is correct if the docstring does not contain
    explicit newlines ('\n') or joined lines ('\' at end of line).

    Leading blank lines are stripped by cleandoc(), so we must
    return the line number of the first non-blank line.
    """
    doc = t.cast(str, get_str_value(node))
    lineno = node.lineno
    if _string_lineno_is_end:
        # In older CPython versions, the AST only tells us the end line
        # number and we must approximate the start line number.
        # This approximation is correct if the docstring does not contain
        # explicit newlines ('\n') or joined lines ('\' at end of line).
        lineno -= doc.count("\n")

    # Leading blank lines are stripped by cleandoc(), so we must
    # return the line number of the first non-blank line.
    for ch in doc:
        if ch == "\n":
            lineno += 1
        elif not ch.isspace():
            break

    return lineno


def _extract_docstring_content(node: ast.Str | ast.Constant) -> tuple[str, int]:
    """
    Extract docstring information from an ast node that represents the docstring.

    @returns:
        - The line number of the first non-blank line of the docsring. See L{extract_docstring_linenum}.
        - The docstring to be parsed, cleaned by L{inspect.cleandoc}.
    """
    lineno = _extract_docstring_linenum(node)
    return inspect.cleandoc(t.cast(str, get_str_value(node))), lineno


if sys.version_info[:2] >= (3, 8):
    # Since Python 3.8 "foo" is parsed as ast.Constant.
    def get_str_value(expr: ast.expr) -> str | None:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        return None

else:
    # Before Python 3.8 "foo" was parsed as ast.Str.
    def get_str_value(expr: ast.expr) -> str | None:
        if isinstance(expr, ast.Str):
            return expr.s
        return None


class Parser:
    def __init__(self, state: libstatic.State, options: ParserOptions) -> None:
        self.state = state
        self.options = options

    def unparse(self, expr: ast.expr, is_annotation: bool = True) -> str:
        nexpr = ast.Expr(expr)
        if not self.options.expand_names:
            return t.cast(str, unparse(nexpr).rstrip("\n"))
        state = self.state
        expand_expr = state.expand_expr
        # expand_name = partial(state.expand_name, 
        #                       scope=next(s for s in state.get_all_enclosing_scopes(expr) 
        #                                  if not isinstance(s, libstatic.Func)), 
        #                       is_annotation=True)

        class SourceGenerator(astor.SourceGenerator):  # type:ignore[misc]
            def visit_Name(self, node: ast.Name) -> None:
                expanded: str = expand_expr(node)
                if expanded and not expanded.endswith('*'):
                    self.write(expanded)
                    return
                # not needed until the parse support unstringed type annotations.
                # elif is_annotation:
                #     expanded = expand_name(node.id)
                #     if expanded and not expanded.endswith('*'):
                #         self.write(expanded)
                #         return
                self.write(node.id)

            def visit_Str(self, node: ast.Str) -> None:
                # astor uses tripple quoted strings :/
                # but we're loosing the precedence infos here, is it important?
                self.write(unparse(ast.Expr(node)).rstrip("\n"))

            def visit_Constant(self, node: ast.Constant) -> None:
                self.write(unparse(ast.Expr(node)).rstrip("\n"))

        try:
            return t.cast(str, astor.to_source(nexpr, source_generator_class=SourceGenerator).rstrip("\n"))
        except Exception:
            return t.cast(str, unparse(nexpr).rstrip("\n"))

    def _get_lineno(self, definition: libstatic.Def) -> int:
        # since ast.alias node only have a lineno info since python 3.10
        # wee need to use parent's lineno for those nodes.
        if isinstance(definition, libstatic.Mod):
            return 0
        current = definition.node
        while True:
            lineno = getattr(current, "lineno", None)
            current = self.state.get_parent(current)
            if lineno is not None:
                break
        return lineno or -1

    def _yield_members(self, definition: libstatic.Def) -> t.Sequence[libstatic.Def]:
        # locals are groupped by name for faster nam lookups, so we need
        # to sort them by source code order here.
        state = self.state
        list_of_defs: list[list[libstatic.Def]] = []
        for name, defs in state.get_locals(definition).items():
            # they can be None values here :/
            defs = list(filter(None, defs))
            if not defs:
                continue
            if (name == '__all__' and isinstance(definition, libstatic.Mod) and
                self.state.get_dunder_all(definition) is not None):
                # take advantage of the fact the __all__ values are parsed
                # by libstatic and output the computed value here, so we leave
                # only one definition of __all__ here and special case-it later.
                defs = [defs[-1]]
            list_of_defs.append(defs)
        # filter unreachable defs if it doesn't remove all
        # information we have about this symbol.
        for defs in list_of_defs:
            # This will contain several definitions if functions are using @overload
            # or simply have several concurrent definitions.
            live_defs = (d for d in defs if d and state.is_reachable(d))
            keep = []
            try:
                keep.append(next(live_defs))
            except StopIteration:
                keep = defs
            else:
                keep.extend(live_defs)
            for d in set(defs).difference(keep):
                defs.remove(d)
        return sorted(chain.from_iterable(list_of_defs), key=lambda d: self._get_lineno(d))

    @staticmethod
    def get_docstring_node(node: ast.AST) -> ast.Str | ast.Constant | None:
        """
        Return the docstring node for the given node or None if no docstring can
        be found.
        """
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef, ast.Module)) or not node.body:
            return None
        node = node.body[0]
        if isinstance(node, ast.Expr) and get_str_value(node.value) is not None:
            return t.cast("ast.Str | ast.Constant", node.value)
        return None

    def get_assign_docstring_node(self, assign: ast.Assign | ast.AnnAssign) -> ast.Str | ast.Constant | None:
        """
        Get the docstring for a L{ast.Assign} or L{ast.AnnAssign} node.
        This helper function relies on the non-standard C{.parent} attribute on AST nodes
        to navigate upward in the tree and determine this node direct siblings.
        """
        parent_node = self.state.get_parent(assign)
        for fieldname, value in ast.iter_fields(parent_node):
            if isinstance(value, (list, tuple)) and assign in value:
                break
        else:
            raise RuntimeError(f"node {assign} not found in {parent_node}")
        body = getattr(parent_node, fieldname)
        if body:
            assert isinstance(body, list)
            assign_index = body.index(assign)
            try:
                right_sibling = body[assign_index + 1]
            except IndexError:
                return None
            if isinstance(right_sibling, ast.Expr) and get_str_value(right_sibling.value) is not None:
                return t.cast("ast.Str|ast.Constant", right_sibling.value)
        return None

    def _extract_comment_docstring(self, definition: libstatic.Def) -> tuple[str | None, int]:
        return None, 0
        # >>> ast.dump(ast_comments.parse('# hello\nclass C: # hello2\n # hello 3\n var=True#false'))
        # "Module(body=[
        # Comment(value='# hello', inline=False),
        # ClassDef(name='C', bases=[], keywords=[],
        # body=[Comment(value='# hello2', inline=True),
        #       Comment(value='# hello 3', inline=False),
        #       Assign(targets=[Name(id='var', ctx=Store())], value=Constant(value=True)),
        #       Comment(value='#false', inline=True)], decorator_list=[])], type_ignores=[])"

    def _compute_instance_vars(self, definition: libstatic.Cls) -> t.Sequence[IVar]:
        class ClassVisitor(LocalStmtVisitor):  # type:ignore[misc]
            def __init__(self) -> None:
                self.ivars: t.List[IVar] = []

            def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                args = node.args.args
                if (
                    len(args) == 0
                    or node.name == "__new__"
                    or any(
                        (
                            state.expand_expr(d)
                            or getattr(d, "id", None)
                            in {"builtins.classmethod", "builtins.staticmethod", "classmethod", "staticmethod"}
                            for d in node.decorator_list
                        )
                    )
                ):
                    # not an instance method
                    return
                self_def = state.get_def(args[0])
                for use in self_def.users():
                    attr = state.get_parent(use)
                    if not (isinstance(attr, ast.Attribute) and isinstance(attr.ctx, ast.Store)):
                        continue
                    self.ivars.append(IVar(attr))

            visit_AsyncFunctionDef = visit_FunctionDef

        state = self.state
        visitor = ClassVisitor()
        visitor.visit(definition.node)
        return visitor.ivars

    def _parse_location(self, definition: libstatic.Def) -> docspec.Location:
        return docspec.Location(
            filename=self.state.get_filename(definition) or "?",
            lineno=self._get_lineno(definition),
            endlineno=getattr(definition.node, "end_lineno", None) if isinstance(definition, libstatic.Scope) else None,
        )

    def _extract_docstring(self, definition: libstatic.Def) -> docspec.Docstring | None:
        if isinstance(definition, (libstatic.Func, libstatic.Mod, libstatic.Cls)):
            doc_node = self.get_docstring_node(definition.node)
        else:
            try:
                doc_node = self.get_assign_docstring_node(
                    self.state.get_parent_instance(definition.node, (ast.Assign, ast.AnnAssign))
                )
            except libstatic.StaticException:
                doc_node = None
        docstring: str | None
        if doc_node:
            docstring, lineno = _extract_docstring_content(doc_node)
        else:
            docstring, lineno = self._extract_comment_docstring(definition)

        if docstring:
            return docspec.Docstring(
                location=docspec.Location(
                    filename=self.state.get_filename(definition) or "?",
                    lineno=lineno,
                    endlineno=None,
                ),
                content=docstring.rstrip(),
            )
        return None

    def _extract_bases(self, definition: libstatic.Cls) -> list[str]:
        return [self.unparse(e) for e in definition.node.bases]

    def _extract_metaclass(self, definition: libstatic.Cls) -> str | None:
        for k in definition.node.keywords:
            if k.arg == "metaclass":
                return self.unparse(k.value)
        if "__metaclass__" not in self.state.get_locals(definition):
            return None
        try:
            metaclass_var, *_ = self.state.get_local(definition, "__metaclass__")
            metaclass_value = get_stored_value(
                metaclass_var.node, self.state.get_parent_instance(metaclass_var.node, (ast.Assign, ast.AnnAssign))
            )
        except libstatic.StaticException:
            return None
        if metaclass_value:
            return self.unparse(metaclass_value)
        return None

    def _extract_return_type(self, returns: ast.expr | None) -> str | None:
        return self.unparse(returns, is_annotation=True) if returns else None

    def _unparse_keywords(self, keywords: list[ast.keyword]) -> t.Iterable[str]:
        for n in keywords:
            yield (f"{(n.arg+'=') if n.arg else '**'}" f"{self.unparse(n.value) if n.value else ''}")

    def _parse_decoration(self, expr: "ast.expr") -> docspec.Decoration:
        if isinstance(expr, ast.Call):
            name = self.unparse(expr.func)
            arglist = [*(self.unparse(n) for n in expr.args), *self._unparse_keywords(expr.keywords)]
        else:
            name = self.unparse(expr)
            arglist = []
        return docspec.Decoration(location=self._parse_location(self.state.get_def(expr)), name=name, arglist=arglist)

    def _extract_semantics_hints(self, definition: libstatic.Def) -> list[object]:
        return []  # TODO: support other semantics hints

    def _parse_ivar(self, ivar: IVar) -> docspec.Variable:
        attrdef = self.state.get_def(ivar.node)
        value, datatype = self._extract_variable_value_type(attrdef)
        return docspec.Variable(
            location=self._parse_location(attrdef),
            docstring=self._extract_docstring(attrdef),
            name=ivar.node.attr,
            datatype=datatype,
            value=value,
            semantic_hints=[docspec.VariableSemantic.INSTANCE_VARIABLE],
        )

    def _parse_argument(self, arg: ArgSpec) -> docspec.Argument:
        return docspec.Argument(
            location=self._parse_location(self.state.get_def(arg.node)),
            name=arg.node.arg,
            type=arg.type,
            datatype=self.unparse(arg.node.annotation, is_annotation=True) if arg.node.annotation else None,
            default_value=self.unparse(arg.default) if arg.default else None,
        )

    def _extract_variable_value_type(self, definition: libstatic.Def) -> tuple[str | None, str | None]:
        # special-case __all__
        scope = self.state.get_enclosing_scope(definition)
        if definition.name() == '__all__' and isinstance(scope, libstatic.Mod):
            computed_value = self.state.get_dunder_all(scope)
            if computed_value is not None:
                return (repr(computed_value), None)
        try:
            assign = self.state.get_parent_instance(definition.node, (ast.Assign, ast.AnnAssign))
        except libstatic.StaticException:
            return None, None
        if isinstance(assign, ast.AnnAssign):
            return (self.unparse(assign.value) if assign.value else None, self.unparse(assign.annotation, is_annotation=True))
        try:
            value = get_stored_value(definition.node, assign)
        except libstatic.StaticException:
            return (None, None)
        annotation = None
        if value is assign.value:
            pass  # TODO: seek for type comment
        if annotation is None:
            # because the code is unfinished, 'self.unparse(annotation)' will never run and mypy complains
            pass  # TODO: do basic type inference
        return (self.unparse(value), self.unparse(annotation, is_annotation=True) if annotation else None)  # type:ignore

    # @t.overload
    # def parse(self, definition: libstatic.Mod) -> docspec.Module:
    #     ...

    # @t.overload
    # def parse(self, definition: libstatic.Def) -> (docspec.Variable | docspec.Function |  # type:ignore
    #                                                docspec.Class | docspec.Indirection):
    #     ...

    def parse(self, definition: libstatic.Def) -> docspec.ApiObject:
        if isinstance(definition, libstatic.Mod):
            return docspec.Module(
                name=definition.name(),
                location=self._parse_location(definition),
                docstring=self._extract_docstring(definition),
                members=[self.parse(m) for m in self._yield_members(definition)],  # type: ignore[misc]
            )
        elif isinstance(definition, libstatic.Cls):
            decorators = definition.node.decorator_list
            metaclass = self._extract_metaclass(definition)
            return docspec.Class(
                name=definition.name(),
                location=self._parse_location(definition),
                docstring=self._extract_docstring(definition),
                members=[
                    *(  # type: ignore[list-item]
                        self.parse(m)
                        for m in self._yield_members(definition)
                        if not metaclass or m.name() != "__metaclass__"
                    ),
                    *(self._parse_ivar(iv) for iv in self._compute_instance_vars(definition)),
                ],
                bases=self._extract_bases(definition),
                metaclass=metaclass,
                decorations=[self._parse_decoration(dec) for dec in decorators] if decorators else None,
                semantic_hints=t.cast(list[docspec.ClassSemantic], self._extract_semantics_hints(definition)),
            )
        elif isinstance(definition, libstatic.Func):
            decorators = definition.node.decorator_list
            return docspec.Function(
                name=definition.name(),
                location=self._parse_location(definition),
                docstring=self._extract_docstring(definition),
                decorations=[self._parse_decoration(dec) for dec in decorators],
                semantic_hints=t.cast(list[docspec.FunctionSemantic], self._extract_semantics_hints(definition)),
                modifiers=["async"] if isinstance(definition.node, ast.AsyncFunctionDef) else None,
                args=[self._parse_argument(arg) for arg in _iter_arguments(definition.node.args)],
                return_type=self._extract_return_type(definition.node.returns),
            )
        elif isinstance(definition, libstatic.Var):
            value, datatype = self._extract_variable_value_type(definition)
            return docspec.Variable(
                name=definition.name(),
                location=self._parse_location(definition),
                docstring=self._extract_docstring(definition),
                semantic_hints=t.cast(list[docspec.VariableSemantic], self._extract_semantics_hints(definition)),
                modifiers=[],
                value=value,
                datatype=datatype,
            )
        elif isinstance(definition, libstatic.Imp):
            return docspec.Indirection(
                name=definition.name(),
                location=self._parse_location(definition),
                target=definition.target(),
                docstring=None,
            )
        else:
            assert False, f"unexpected definition type: {type(definition)}"
