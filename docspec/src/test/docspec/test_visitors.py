import docspec
from .fixtures import module

def test_visitors(capsys, module: docspec.Module) -> None:

    visitor = docspec.PrintVisitor(colorize=False)
    module.walk(visitor)
    captured = capsys.readouterr().out
    assert captured == """:0 - Module: a
| :0 - Class: foo
| | :0 - Data: val
| | :0 - Function: __init__
"""
    
    predicate = lambda ob: not isinstance(ob, docspec.Data) # removes any Data entries

    filter_visitor = docspec.FilterVisitor(predicate)
    module.walk(filter_visitor)
    module.walk(visitor)
    captured = capsys.readouterr().out
    assert captured == """:0 - Module: a
| :0 - Class: foo
| | :0 - Function: __init__
"""

