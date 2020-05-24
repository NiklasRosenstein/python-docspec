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
__version__ = '0.0.2'
__all__ = ['parse_python', 'Parser']

from .parser import Parser
from docspec import Module
from typing import Any, TextIO, Union


def parse_python(
    f: Union[str, TextIO],
    filename: str = None,
    module_name: str = None,
    **options: Any,
) -> Module:
  """
  Parses Python code of a file or file-like object and returns a #Module
  object with the contents of the file The *options* are forwarded to the
  #Parser constructor.
  """

  if isinstance(f, str):
    with open(f) as fp:
      return parse_python(fp, filename, module_name, **options)

  filename = filename or getattr(f, 'name', None)
  parser = Parser(**options)
  ast = parser.parse_to_ast(f.read(), filename)
  return parser.parse(ast, filename, module_name)
