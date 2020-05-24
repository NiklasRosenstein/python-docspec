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

from docspec_python import parse_python
import argparse
import docspec
import sys


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('file', nargs='?')
  parser.add_argument('-n', '--name', help='The name of the module that is being parsed. If not specified, it is derived from the filename.')
  parser.add_argument('-t', '--tty', action='store_true', help='Enable reading from stdin if it is a TTY.')
  parser.add_argument('-2', '--python2', action='store_true', help='Parse as Python 2 source (parse print as a statement).')
  parser.add_argument('--treat-singleline-comment-blocks-as-docstrings', action='store_true')
  args = parser.parse_args()

  if not args.file and sys.stdin.isatty() and not args.tty:
    parser.print_usage()
    sys.exit(1)

  options = {
    'module_name': args.name,
    'print_function': not args.python2,
    'treat_singleline_comment_blocks_as_docstrings': args.treat_singleline_comment_blocks_as_docstrings,
  }

  module = parse_python(args.file or sys.stdin, **options)
  docspec.dump_module(module, sys.stdout)


if __name__ == '__main__':
  main()
