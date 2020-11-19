  [docspec]: https://github.com/NiklasRosenstein/docspec

# docspec-python

A parser based on `lib2to3` procuding [docspec][] data from Python source code.

Example:

```
from docspec_python import parse_python_module
import docspec, sys
docspec.dump_module(parse_python_module(sys.stdin, print_function=False), sys.stdout)
```

```
$ docspec-python -p docspec | docspec --dump-tree --multiple | head
module __init__
| data __author__
| data __version__
| data __all__
| data _ClassProxy
| data _mapper
| class Location
| | data filename
| | data lineno
| class Decoration
```

---

<p align="center">Copyright &copy; 2020, Niklas Rosenstein</p>
