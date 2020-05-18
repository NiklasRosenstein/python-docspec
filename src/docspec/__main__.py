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

import docspec
import argparse
import sys


def _dump_tree(obj: docspec._Base, depth: int = 0):
  print('| ' * depth + type(obj).__name__.lower(), obj.name)
  for member in getattr(obj, 'members', []):
    _dump_tree(member, depth+1)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('file', nargs='?')
  parser.add_argument('--multiple', action='store_true')
  parser.add_argument('--dump-tree', action='store_true')
  args = parser.parse_args()

  if args.multiple:
    modules = list(docspec.load_modules(args.file or sys.stdin))
  else:
    modules = [docspec.load_module(args.file or sys.stdin)]

  if args.dump_tree:
    for module in modules:
      _dump_tree(module)
  else:
    for module in modules:
      docspec.dump_module(module, sys.stdout)


if __name__ == '__main__':
  main()
