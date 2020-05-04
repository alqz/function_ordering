doc = f"""Reorders a file's functions via postorder traversal of the call graph."""


class Parser:
    @staticmethod
    def find_next_function(lines, line_number):
        """
        Find the function start at or after `line_number` in `lines`.

        Return `None` if no functions until end.

        Otherwise, return a tuple containing
         1. `i` the line number of the start of the function;
         2. the function name; and
         3. `n` the number of lines in that function definition,
            such that `i + n` is the index right after the end.
        """
        assert False, "Unimplemented!"

    @staticmethod
    def contains_reference(line, function_name):
        """
        Return `True` iff `line` contains a reference of `function_name`.
        """
        assert False, "Unimplemented!"

    @staticmethod
    def is_start_marker(line):
        """
        Return `True` iff `line` is the start marker.
        Sorting applies to lines after the first start marker.
        """
        assert False, "Unimplemented!"

    @staticmethod
    def is_end_marker(line):
        """
        Return `True` iff `line` contains the end marker.
        Sorting applies to lines before the last end marker.
        """
        assert False, "Unimplemented!"


class PythonParser(Parser):
    @staticmethod
    def _get_all_identifer_chars():
        abc = "abcdefghijklmnopqrstuvwxyz"
        digits = "0123456789"
        s = set()
        s.update(abc)
        s.update(abc.upper())
        s.update(digits)
        s.add("_")
        return s

    all_identifier_chars = _get_all_identifer_chars.__func__()

    @staticmethod
    def _get_name_if_def(s):
        if s[:4] == "def ":
            end = s.find("(")
            function_name = s[4:end]
            assert " " not in function_name
            return function_name
        return None

    @staticmethod
    def _is_indented_text(s):
        all_spaces = all([c == " " for c in s])
        return len(s) >= 4 and s[:4] == "    " and not all_spaces

    @staticmethod
    def _find_next_def(lines, line_number):
        """Includes line at line_number."""
        for i in range(line_number, len(lines)):
            function_name = PythonParser._get_name_if_def(lines[i])
            if function_name:
                return (i, function_name)
        return None

    @staticmethod
    def find_next_function(lines, line_number):
        next_def = PythonParser._find_next_def(lines, line_number)
        if next_def is None:
            return None
        i, function_name = next_def
        next_def = PythonParser._find_next_def(lines, i + 1)
        if next_def is None:
            end = len(lines)
        else:
            end, _ = next_def
        for j in range(end - 1, i, -1):
            if PythonParser._is_indented_text(lines[j]):
                break
        n = j - i + 1
        return i, function_name, n

    @staticmethod
    def contains_reference(line, function_name):
        if not PythonParser._is_indented_text(line):
            return False
        i = line.find(function_name)
        if i == -1:
            return False
        if line[i - 1] in PythonParser.all_identifier_chars:
            return False
        after_index = i + len(function_name)
        if len(line) == after_index:
            return True
        assert len(line) > after_index
        if line[after_index] in PythonParser.all_identifier_chars:
            return False
        return True

    @staticmethod
    def _contains_in_comment(s, comment_text):
        comment_start = s.find("#")
        if comment_start == -1:
            return False
        text_start = s.find(comment_text, comment_start)
        return text_start != -1

    @staticmethod
    def is_start_marker(line):
        return PythonParser._contains_in_comment(line, "fsort:start")

    @staticmethod
    def is_end_marker(line):
        return PythonParser._contains_in_comment(line, "fsort:end")


class Graph:
    @staticmethod
    def postorder_traversal(g, start):
        visited = set()
        result = []

        def visit(n):
            visited.add(n)
            [visit(child) for child in g[n] if child not in visited]
            result.append(n)
        visit(start)
        return result

    @staticmethod
    def find_sources(g, ignore_loops=False):
        invalidated = set()
        for n in g:
            for child in g[n]:
                if child != n:
                    invalidated.add(child)
        return set(g.keys()) - invalidated


USE_PARSER = PythonParser


# fsort:start


def mod_lines_between_markers(lines, mod):
    start = 0
    for i in range(len(lines)):
        if USE_PARSER.is_start_marker(lines[i]):
            start = i + 1
    end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if USE_PARSER.is_end_marker(lines[i]):
            end = i
    return lines[:start] + mod(lines[start:end]) + lines[end:]


def partition_by_function(lines, partition_finder):
    partitions = []
    c = 0
    while True:
        next_partition = partition_finder(lines, c)
        if next_partition is None:
            break
        i, function_name, n = next_partition
        partitions.append((i, function_name, i + n))
        c = i + 1
    return partitions


def search_for_references(lines, start, end, function_name):
    refs = []
    for i in range(start, end):
        if USE_PARSER.contains_reference(lines[i], function_name):
            refs.append(i)
    return refs


def get_call_mapping(lines, partitions):
    mapping = {}
    all_function_names = [f for _, f, _ in partitions]
    assert len(all_function_names) == len(set(all_function_names))
    for start, function_name, end in partitions:
        called_functions = [
            f for f in all_function_names if search_for_references(
                lines, start, end, f) != []]
        mapping[function_name] = called_functions
    return mapping


def reorder_lines(lines, partitions, ordered_function_names):
    order_spec = {
        ordered_function_names[i]: i for i in range(
            len(ordered_function_names))}
    c = 0
    acc = []
    # We need starts to be right after the end of the previous, rather than
    # where 'def' is.
    for start, function_name, end in partitions:
        acc.append((order_spec[function_name], c, end))
        c = end
    new_lines = []
    for _, start, end in sorted(acc):
        new_lines += lines[start:end]
    # Append the rest of the lines occuring after the last function
    new_lines += lines[c:]
    return new_lines


def reorder_lines_by_function_calls(lines, reverse):
    partitions = partition_by_function(lines, USE_PARSER.find_next_function)
    m = get_call_mapping(lines, partitions)
    sources = Graph.find_sources(m, ignore_loops=True)
    m["."] = sorted(list(sources))
    traversal = Graph.postorder_traversal(m, ".")
    assert traversal.pop() == "."
    ordered_function_names = list(traversal)
    if reverse:
        ordered_function_names = list(reversed(ordered_function_names))
    return reorder_lines(lines, partitions, ordered_function_names)


def write_lines(file_path, lines):
    with open(file_path, "w") as f:
        for line in lines:
            f.write(line)
            f.write("\n")


# fsort:end


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument('--reverse', action='store_true',
                        help="reverse the ordering")
    parser.add_argument('--in-place', action='store_true',
                        help="make changes to file in place")
    parser.add_argument('file', action='store', help="file to reorder")
    args = parser.parse_args()
    with open(args.file) as f:
        lines = f.read().splitlines()

    def mod(lines): return reorder_lines_by_function_calls(lines, args.reverse)
    new_lines = mod_lines_between_markers(lines, mod)
    if args.in_place:
        write_lines(args.file, new_lines)
    else:
        for line in new_lines:
            print(line)
