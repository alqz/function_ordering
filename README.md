# Function Ordering

Reorders a file's functions via postorder traversal of the call graph.


## Usage

```
usage: reorder.py [-h] [--reverse] [--in-place] file

Reorders a file's functions via postorder traversal of the call graph.

positional arguments:
  file        file to reorder

optional arguments:
  -h, --help  show this help message and exit
  --reverse   reverse the ordering
  --in-place  make changes to file in place
```

The default language is Python.

The range of lines to be reordered begins at the first instance of `fsort:start` and ends at the last instance of `fsort:end` within the target file.


## Language support

The default language and the only one with built-in support is Python.

The parsing is not AST-based. Only orders functions defined at the top level. This can be customized.

To customize or to add your own language, implement a subclass of the `Parser` class and change the value of `USE_PARSER` to the name of your own class.

The crucial methods to implement are `find_next_function` and `contains_reference`. See `reorder.py` for their specifications.


## Ordering details

Postorder traversal (or its reverse) of the call graph is usually the best ordering of functions.

It happens that ties are broken by the calling order within function bodies. Functions not called by other functions in the same file are sorted alphabetically.