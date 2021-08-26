#!/bin/bash

echo
echo "__Table of Contents__"
echo
echo "* [Changelog](#changelog)"
echo "* [docspec Changelog](#docspec-changelog)"
echo "* [docspec_python Changelog](#docspec_python-changelog)"
echo

echo
echo '# Changelog'
echo
shut changelog -a --markdown

echo
echo '# docspec Changelog'
echo
shut -C docspec changelog -a --markdown

echo
echo '# docspec_python Changelog'
echo
shut -C docspec-python changelog -a --markdown
