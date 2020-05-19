# docspec

This Python packages provides

* A library to (de-) serialize Docspec conformat JSON payloads
* A CLI to validate and introspect such payloads

Example:

```py
import docspec, sys
for module in docspec.load_modules(sys.stdin):
  module.members = [member for member in module.members if member.docstring]
  docspec.dump_module(sys.stdout)
```

```
$ docspec module.json --dump-tree
module docspec
| class Location
| | data filename
| | data lineno
| class Decoration
| | data name
# ...
```

The `docspec` Python module requires Python 3.5 or newer.

---

<p align="center">Copyright &copy; 2020, Niklas Rosenstein</p>
