




# Docspec JSON Specification


## Struct `Location`

The location object describes where the an API object was extracted from a file. Uusally this points to the source file and a line number. The filename should always be relative to the root of a project or source control repository.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `filename` | `str` | Yes | A relative filename (e.g. relative to the project root). |
| `lineno` | `int` | Yes | The line number in the *filename* from which the API object was parsed. |


## Struct `Docstring`

Represents the documentation string of an API object.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `content` | `str` | Yes | The content of the docstring. |
| `location` | `Optional[Location]` | No | The location where the docstring is defined. This points at the position of the first character in the *content* field. |


## Struct `Indirection`

Represents an imported name. It can be used to resolve references to names in the API tree to fully qualified names.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `str` | Yes | The value is `"indirection"`. |
| `name` | `str` | Yes | The name that is made available in the scope of the parent object. |
| `location` | `Optional[Location]` | No | The location where the indirection is defined. |
| `target` | `str` | Yes | The target to which the name points. In the case of Python for example this can be a fully qualified name pointing to a member or a member of a module. In the case of starred imports, the last part is a star (as in `os.path.*`). |


## Struct `Data`

A `Data` object represents a variable or constant.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `str` | Yes | The value is `"data"`. |
| `name` | `str` | Yes | The name of the variable or constant. |
| `location` | `Optional[Location]` | No | The location where the variable or constant is defined. |
| `docstring` | `Optional[Docstring]` | No | The docstring of the variable or constant. |
| `datatype` | `Optional[str]` | No | The name of the type of the variable or constant. |
| `value` | `Optional[str]` | No | The value that is assigned to this variable or constant as source code. |
| `modifiers` | `Optional[List[str]]` | No | A list of modifier keywords used in the source code to define this variable or constant, like `const`, `static`, `final`, `mut`, etc. |
| `semantic_hints` | `List[DataSemantic]` | No | A list of behavioral properties for this variable or constant. |


## Enumeration `DataSemantic`

Describes possible behavioral properties of a variable or constant.

* `INSTANCE_VARIABLE` &ndash; 
* `CLASS_VARIABLE` &ndash; 
* `CONSTANT` &ndash; 


## Struct `Argument`

Represents a function argument.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `ArgumentType` | Yes | The type of argument. |
| `name` | `str` | Yes | The name of the argument. |
| `datatype` | `Optional[str]` | No | The data type of the argument. |
| `default_value` | `Optional[str]` | No | The default value of the argument as a code string. |


## Enumeration `ArgumentType`



* `POSITIONAL_ONLY` &ndash; An argument that can only be given by its position in the argument list. In Python, these are arguments preceeding a `/` marker in the argument list. Many programming languages support only one type of positional arguments. Loaders for such languages should prefer the `POSITIONAL` argument type over `POSITIONAL_ONLY` to describe these type of arguments.
* `POSITIONAL` &ndash; 
* `POSITIONAL_REMAINDER` &ndash; 
* `KEYWORD_ONLY` &ndash; 
* `KEYWORD_REMAINDER` &ndash; 


## Struct `Decoration`

Represents a decoration that can be applied to a function or class.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `name` | `Optional[str]` | Yes | The name of the decorator used in this decoration. This may be `null` if the decorator can not be represented simply by a name, e.g. in Python 3.9 where decorators can be full fledged expressions. In that case the `raw_expression` field is used instead. |
| `args` | `Optional[List[str]]` | No | A list of the raw source code for each argument of the decorator. If this is not set, that means the decorator is not called. If the list is empty, the decorator is called without arguments. |
| `raw_expression` | `Optional[List[str]]` | No | The raw code string that represents the decorator that is used for this expression. This is used if the decorator can not be represented by just a `name`. The `args` may still be used if the expression gets called (e.g. in the case of `@(decorator_factory().dec)(a, b, c)`, the `raw_expression` should be `"(decorator_factory().dec)"` whereas the `args` should be `["a", "b", "c"]`. |


## Struct `Function`

Represents a function definition in a module or class.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `str` | Yes | Value is `"function"` |
| `name` | `str` | Yes | The name of the function. |
| `location` | `Optional[Location]` | No |  |
| `docstring` | `Optional[Docstring]` | No |  |
| `modifiers` | `Optional[List[str]]` | No | An list of modifier keywords that the function was defined with. |
| `args` | `List[Argument]` | Yes | The function arguments. |
| `return_type` | `Optional[str]` | No | The return type of the function. |
| `decorations` | `Optional[List[Decoration]]` | No | The list of decorations attached to the function. |
| `semantic_hints` | `List[FunctionSemantic]` | No | A list of behavioral properties for this function. |


## Enumeration `FunctionSemantic`



* `ABSTRACT` &ndash; 
* `FINAL` &ndash; 
* `COROUTINE` &ndash; 
* `NO_RETURN` &ndash; 
* `INSTANCE_METHOD` &ndash; 
* `CLASS_METHOD` &ndash; 
* `STATIC_METHOD` &ndash; 
* `PROPERTY_GETTER` &ndash; 
* `PROPERTY_SETTER` &ndash; 
* `PROPERTY_DELETER` &ndash; 


## Struct `Class`

Represents a class definition.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `str` | Yes | The value is `"class"`. |
| `name` | `str` | Yes | The name of the class. |
| `location` | `Optional[Location]` | No |  |
| `docstring` | `Optional[Docstring]` | No |  |
| `metaclass` | `Optional[str]` | No | The name of the metaclass used in this class definition. |
| `bases` | `Optional[List[str]]` | No | A list of the base classes that the class inherits from. |
| `members` | `List[Data \| Function \| Class]` | Yes | A list of the members of the class. |
| `decorations` | `Optional[List[Decoration]]` | No | A list of the decorations applied to the class definition. |
| `modifiers` | `Optional[List[str]]` | No | A list of the modifier keywords used to declare this class. |
| `semantic_hints` | `List[ClassSemantic]` | No | A list of the semantic hints for this class. |


## Enumeration `ClassSemantic`



* `INTERFACE` &ndash; 
* `ABSTRACT` &ndash; 
* `FINAL` &ndash; 
* `ENUM` &ndash; 


## Struct `Module`

A module represents a collection of data, function and classes. In the Python language, it represents an actual Python module. In other languages it may refer to another file type or a namespace.

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `str` | Yes | The value is `"module"`. |
| `name` | `str` | Yes | The name of the module. The name is supposed to be relative to the parent. |
| `location` | `Optional[Docstring]` | No | The location of the module. Usually the line number will be `0`. |
| `docstring` | `Optional[Docstring]` | No | The docstring for the module as parsed from the source. |
| `members` | `List[Class \| Data \| Function \| Module]` | Yes | A list of the module members. |


