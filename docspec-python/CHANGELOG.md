# Changelog

## v0.0.3

* Rename `parse_python()` to `parse_python_module()`
* Add `find_module()` and `iter_package_files()` functions
* Add `ParserOptions` instead of options mapping
* When the `Module.name` is derived from the filename, use the directory name if the filename
  is `__init__.py`
