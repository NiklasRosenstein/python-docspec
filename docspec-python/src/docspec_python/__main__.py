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

from docspec_python import discover, load_python_modules, ParserOptions, DiscoveryResult
import argparse
import docspec
import sys


def main():
  parser = argparse.ArgumentParser(
    formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=34, width=100),
  )
  group = parser.add_argument_group('input options')
  group.add_argument('-m', '--module', action='append', metavar='MODULE', help='parse the specified module.')
  group.add_argument('-p', '--package', action='append', metavar='MODULE', help='parse the specified module and submodules.')
  group.add_argument('-I', '--search-path', metavar='PATH', action='append', help='override the module search path. defaults to sys.path.')
  group.add_argument('-D', '--discover', action='store_true', help='discover available packages in the search path.')
  group.add_argument('-E', '--exclude', action='append', help='exclude modules/packages when using --discover.')
  group = parser.add_argument_group('parsing options')
  group.add_argument('-2', '--python2', action='store_true', help='parse as python 2 source.')
  group.add_argument('--treat-singleline-comment-blocks-as-docstrings', action='store_true',
    help='parse blocks of single-line comments as docstrings for modules, classes and functions.')
  group = parser.add_argument_group('output options')
  group.add_argument('-l', '--list', action='store_true', help='list modules from the input.')
  args = parser.parse_args()

  args.module = args.module or []
  args.package = args.package or []

  if args.discover:
    for path in (args.search_path or sys.path):
      try:
        discovered_items = list(discover(path))
      except FileNotFoundError:
        continue
      for item in discovered_items:
        if args.exclude and item.name in args.exclude:
          continue
        if isinstance(item, DiscoveryResult.Module):
          args.module.append(item.name)
        elif isinstance(item, DiscoveryResult.Package):
          args.package.append(item.name)
        else:
          raise RuntimeError(item)

  if not args.module and not args.package:
    parser.print_usage()
    sys.exit(1)

  options = ParserOptions(
    print_function=not args.python2,
    treat_singleline_comment_blocks_as_docstrings=args.treat_singleline_comment_blocks_as_docstrings,
  )
  modules = load_python_modules(args.module, args.package, args.search_path, options)

  if args.list:
    for module in sorted(modules, key=lambda x: x.name):
      print('| ' * module.name.count('.') + module.name.rpartition('.')[-1])
    return

  for module in modules:
    docspec.dump_module(module, sys.stdout)


if __name__ == '__main__':
  main()
