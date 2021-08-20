#!/bin/bash

echo
echo '# docspec Changelog'
echo
shut -C docspec changelog -a --markdown

echo
echo '# docspec_python Changelog'
echo
shut -C docspec-python changelog -a --markdown
