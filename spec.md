# Docspec JSON object specification

__Table of Contents__

* [Location](#location)
* [Module](#module)
* [Class](#class)
* [Data](#data)
* [Function](#function)
* [Argument](#drgument)
* [Decoration](#decoration)

## Object Types

### Location

The location object describes where the an API object was extracted from a
file. Uusally this points to the source file and a line number. The filename
should always be relative to the root of a project or source control repository.

_Fields_

* `filename` (str) &ndash; A relative filename.
* `lineno` (int): &ndash; The line number from which the API object was parsed.

### Module

A module represents a collection of data, function and classes. In the Python
language, it represents an actual Python module. In other languages it may
refer to another file type or a namespace.

_Fields_

* `name` (str) &ndash; The full name of the module.
* `location` (Location)
* `docstring` (Optional[str]) &ndash; The docstring for the module as parsed
  from the source.
* `members` (array) &ndash; An array of `Data`, `Function` or `Class` objects.

### Class

Represents a class definition.

_Fields_

* `type` (str) &ndash; Value is `class`
* `name` (str)
* `location` (Location)
* `docstring` (Optional[str])
* `metaclass` (Optional[str]) &ndash; A string representing the metaclass.
* `bases` (Optional[array]) &ndash; An array of `str` representing the base classes.
* `members` (array) &ndash; An array of `Data`, `Function` or `Class` objects.
* `decorations` (Optional[array]) &ndash; An array of `Decoration` objects.

### Data

A `Data` object represents a static value that is assigned to a name.

_Fields_

* `type` (str) &ndash; Value is `data`.
* `name` (str) &ndash; The name for the value.
* `location` (Location)
* `docstring` (Optional[str])
* `datatype` (Optional[str]) &ndash; The datatype of the value.
* `value` (Optional[str]) &ndash; The value in the form of the definition
  in the source.

### Function

Represents a function definition in a module or class.

_Fields_

* `type` (str) &ndash; Value is `function`
* `name` (str)
* `location` (str)
* `docstring` (Optional[str])
* `modifiers` (Optional[array]) &ndash; An array of `str` representing the modifers
  of this function (e.g. `async`, `classmethod`, etc.).
* `args` (array) &ndash; An array of `Argument` objects.
* `return_type` (Optional[str]) &ndash; The return type of the function.
* `decorations` (Optional[array]) &ndash; An array of `Decoration` objects.

### Argument

Represents a function argument.

_Fields_

* `type` (str) &ndash; One of `PositionalOnly`, `Positional`,
  `PositionalRemainder`, `KeywordOnly` or `KeywordRemainder`.
* `name` (str)
* `datatype` (Optional[str])
* `default_value` (Optional[str])

### Decoration

Represents a decoration that can be applied to a function or class.

_Fields_

* `name` (str) &ndash; The name of the decoration.
* `args` (Optionla[array]) &ndash; An array of `str` representing the arguments
  passed to the decoration. If unset or null, indicates that the decoration was
  not called like a function.

---

<p align="center">Copyright &copy; 2020, Niklas Rosenstein</p>
