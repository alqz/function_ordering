import sys  # isort:skip

sys.path.append("tools/python_libraries/")  # isort:skip

import json
import os
import textwrap

from wamclib.time_conversion import convert_pacific_time_date_to_seconds


def ensure_dir(path, *paths):
    d = os.path.join(path, *paths)
    # Python 3 atomically creates dir if doesn't exist
    os.makedirs(d, exist_ok=True)
    return d


class Util:
    @staticmethod
    def singleton_dict_to_pair(singleton_dict):
        [(k, v)] = singleton_dict.items()
        return (k, v)

    @staticmethod
    def sort_singleton_dict_list(dict_list):
        """
        In place sort, first by dict key then by dict value.

        [{1: 2}, {0: 5}, {1: 1}] becomes [{0: 5}, {1: 1}, {1: 2}]
        """
        dict_list.sort(key=lambda d: Util.singleton_dict_to_pair(d))

    @staticmethod
    def with_open_file(fname, fun):
        f = open(fname, "w+")
        try:
            fun(f)
        except:
            os.remove(fname)
            raise
        finally:
            f.close()

    @staticmethod
    def snake_to_camelcase(value, capitalize_first=False):
        """Converts strings in snake-case naming convention to camel-case.

        foo_bar_baz will be transformed into FooBarBaz by this method. This method
        follows the garbage-in-garbage-out philosophy and will not check that the
        input is sane."""
        words = value.split("_")
        out = ""
        if not capitalize_first and len(words) >= 1:
            out += words[0]
            words = words[1:]
        for word in words:
            out += word.capitalize()
        return out

    @staticmethod
    def snake_to_upper_camelcase(value):
        return snake_to_camelcase(value, capitalize_first=True)


snake_to_camelcase = Util.snake_to_camelcase
snake_to_upper_camelcase = Util.snake_to_upper_camelcase
with_open_file = Util.with_open_file


# fsort:start


# field info for Scuba formatters
def gen_field_info(f, schema):
    s = schema.remove_deprecated()

    def make_info(x):
        # NOTE: including field even if there's just name for consistency and
        # for easy comparison with previous versions
        res = {}

        def copy(name):
            res[name] = x[name]

        def copy_opt(name):
            value = x.get(name)
            if value:
                res[name] = value

        copy("name")
        copy("type")
        copy("data_type")

        copy_opt("doc")
        copy_opt("format")

        return res

    l = [make_info(x) for x in schema.values]
    json.dump(l, f, sort_keys=True, indent=0)


def gen_field_info_for_scuba(schema, output_dir):
    with_open_file(
        os.path.join(output_dir, "field-info.json"), lambda f: gen_field_info(f, schema)
    )


def gen_schema_common(
    schema, properties=[], remove_deprecated=True, remove_server_side=True
):
    schema = schema.apply_properties(properties)

    remove_unreachable = False

    if remove_deprecated:
        schema = schema.remove_deprecated()
        remove_unreachable = True

    if remove_server_side:
        schema = schema.remove_server_side()
        remove_unreachable = True

    if remove_unreachable:
        schema = schema.remove_unreachable()

    return schema


def gen_wam_common(x, d, extra=[]):
    for k in ["name", "doc", "deprecated"] + extra:
        v = x.get(k)
        if v:
            d[k] = v


def gen_wam_enum_constant(x):
    d = {}
    gen_wam_common(x, d)

    d["code"] = x["code"]

    return d


def gen_wam_enum(x):
    d = {}
    gen_wam_common(x, d)

    d["constant_list"] = [gen_wam_enum_constant(c) for c in x["constant"]]

    return d


def singleton_dict_to_pair(singleton_dict):
    [(k, v)] = singleton_dict.items()
    return (k, v)


def sort_singleton_dict_list(dict_list):
    """
    In place sort, first by dict key then by dict value.

    [{1: 2}, {0: 5}, {1: 1}] becomes [{0: 5}, {1: 1}, {1: 2}]
    """
    dict_list.sort(key=lambda d: singleton_dict_to_pair(d))


def gen_wam_properties(x, d, property_names):
    properties = []
    for k, v in x["properties"]:
        if k in property_names:
            properties.append({k: v})
    if properties:
        sort_singleton_dict_list(properties)
        d["property_list"] = properties


def validate_pii_field(d):
    if d.get("pii_field") and not d.get("pii"):
        print(
            "error: %s has .pii set to False but has .pii-field set to %s, set .pii to True or remove the .pii-field"
            % (d.get("name"), d.get("pii_field")),
            file=sys.stderr,
        )
        sys.exit(1)


def gen_wam_global_field(x):
    d = {}

    d["name"] = x["value"]
    d[
        "code"
    ] = 0  # TODO: one day we start assigining unique global field codes from a dedicated codespace
    if x.get("deprecated"):
        d["deprecated"] = True

    gen_wam_properties(x, d, ["table", "platform", "server_side", "temporary"])

    if x.get("pii"):
        d["pii"] = x["pii"]

    if x.get("pii_field"):
        d["pii_field"] = x["pii_field"]

    validate_pii_field(d)

    return d


def gen_value_code(value):
    code = value["code"] << 1

    if value["v1_kind"] == "dimension":
        code |= 1

    return code


def gen_wam_field(x):
    d = {}
    gen_wam_common(x, d, ["all_users", "server_side"])

    d["code"] = gen_value_code(x)

    # override int type for 'event' field
    if x["name"] == "event":
        d["data_type"] = "enum"
        d["type_name"] = "event"
    elif x["name"] in ("loc", "peer_loc"):
        d["data_type"] = "enum"
        d["type_name"] = "loc"
    else:
        d["data_type"] = x["data_type"]
        d["type_name"] = x["type"]

    # XXX: for fields, this is relevant only when field is an attribute
    tags = x.get("tags")
    if tags:
        d["tag_list"] = list(tags)

    # TODO
    # if x.get('is_event'):
    #    d['is_event'] = True

    if x.get("pii"):
        d["pii"] = x["pii"]

    if x.get("pii_field"):
        d["pii_field"] = x["pii_field"]

    if x.get("uii"):
        d["uii"] = x["uii"]

    validate_pii_field(d)

    return d


def gen_wam_optional_fields(x, d, extra):
    for k in extra:
        v = x.get(k)
        if v == False:
            d[k] = v


def gen_wam_event_field(x):
    d = {}

    d["name"] = x["value"]
    d["code"] = x["field_code"]
    if x.get("deprecated"):
        d["deprecated"] = True

    tags = x.get("tags")
    if tags:
        d["tag_list"] = list(tags)

    gen_wam_properties(x, d, ["platform", "server_side", "temporary"])
    gen_wam_optional_fields(
        x, d, ["collect", "forward", "forward-to-scuba", "forward-to-hive"]
    )

    if x.get("pii"):
        d["pii"] = True

    if x.get("pii_field"):
        d["pii_field"] = x["pii_field"]

    if x.get("anomaly_detector"):
        d["anomaly_detector"] = x["anomaly_detector"]

    validate_pii_field(d)

    return d


def gen_wam_event_global_field(name):
    d = {}

    # TODO: how do we allow global event fields to be deprecated?
    d["name"] = name
    d["global"] = True

    return d


def gen_wam_event_field_group(x):
    d = {}

    d["name"] = x["name"]
    if x.get("deprecated"):
        d["deprecated"] = True

    sort_singleton_dict_list(d)
    return d


def gen_wam_event_global_field_group(name):
    d = {}

    # TODO: how do we allow global event field groups to be deprecated?
    d["name"] = name
    d["global"] = True

    return d


def gen_sampling_spec(sampling_spec):
    d = {}
    if sampling_spec.get("name"):
        d["name"] = sampling_spec.get("name")

    if sampling_spec.get("debug_weight"):
        d["debug_weight"] = sampling_spec.get("debug_weight")

    if sampling_spec.get("beta_weight"):
        d["beta_weight"] = sampling_spec.get("beta_weight")

    if sampling_spec.get("release_weight"):
        d["release_weight"] = sampling_spec.get("release_weight")

    if sampling_spec.get("all_weight"):
        d["all_weight"] = sampling_spec.get("all_weight")

    return d


def gen_set_platforms(event):
    res = []
    set_platforms = event.get("set_platform")
    for platform, platform_dict in list(set_platforms.items()):
        d = {}
        d["platform"] = platform
        schema_sampling_spec = platform_dict.get("schema", None)
        event_sampling_spec = platform_dict.get("event", None)

        if event_sampling_spec:
            d["sampling_spec"] = gen_sampling_spec(event_sampling_spec)
        elif schema_sampling_spec:
            d["sampling_spec"] = gen_sampling_spec(schema_sampling_spec)
        res.append(d)
    return res


def gen_event_code(event):
    code = event["code"] << 1
    return code


def gen_wam_event(x):
    d = {}
    gen_wam_common(x, d, ["all_users", "server_side"])

    d["code"] = gen_event_code(x)

    if x.get("all_users_by_default"):
        d["all_users"] = True
        d["all_users_by_default"] = True

    fields = x.get("field", [])
    field_groups = x.get("field_group", [])

    event_global = x["global"]
    global_fields = event_global["field"]
    global_field_groups = event_global["field_group"]

    d["field_list"] = [gen_wam_event_field(f) for f in fields] + [
        gen_wam_event_global_field(f) for f in global_fields
    ]
    d["field_group_list"] = [gen_wam_event_field_group(f) for f in field_groups] + [
        gen_wam_event_global_field_group(f) for f in global_field_groups
    ]

    tags = x.get("tags")
    if tags:
        d["tag_list"] = list(tags)

    expiry_value = x.get("expiry")
    if expiry_value:
        d["expiry"] = convert_pacific_time_date_to_seconds(expiry_value)

    owners = x.get("owner")
    if owners:
        d["owner_list"] = list(owners)

    gen_wam_properties(x, d, ["table", "platform", "server_side", "temporary"])
    gen_wam_optional_fields(
        x, d, ["collect", "forward", "forward-to-scuba", "forward-to-hive"]
    )

    d["set_platform_list"] = gen_set_platforms(x)

    return d


def gen_wam_alias(x):
    d = {}
    gen_wam_common(x, d)

    d["data_type"] = x["data_type"]
    d["type_name"] = x["type"]

    if x.get("value_format"):
        d["value_format"] = x["value_format"]

    return d


def gen_wam_field_group_field(x):
    d = {}

    d["name"] = x["name"]
    if x.get("deprecated"):
        d["deprecated"] = True
    gen_wam_optional_fields(
        x, d, ["collect", "forward", "forward-to-scuba", "forward-to-hive"]
    )

    return d


def gen_wam_field_group(x):
    d = {}
    gen_wam_common(x, d)

    d["field_list"] = [gen_wam_field_group_field(x) for x in x["field"]]

    return d


def gen_wam_table(schema, table_name):
    schema = gen_schema_common(
        schema,
        properties=[("table", table_name)],
        remove_deprecated=False,
        remove_server_side=False,
    )

    event_names = [x["name"] for x in schema.events]

    d = {}
    d["name"] = table_name
    d["event_list"] = event_names

    return d


def gen_wam_schema(f, schema, properties=[]):
    schema = gen_schema_common(
        schema, properties=properties, remove_deprecated=False, remove_server_side=False
    )

    events = [gen_wam_event(x) for x in schema.events]
    fields = [gen_wam_field(x) for x in schema.values]
    enums = [gen_wam_enum(x) for x in schema.enums]
    aliases = [gen_wam_alias(x) for x in schema.aliases]

    # TODO: this is added for backward compatibility with the older schema
    # version -- it will no longer be needed after we fully switch to groups
    common_attributes = [
        x
        for x in schema.common_attributes
        if x["name"] not in ("event", "user_id", "user_weight", "weight")
    ]

    # TODO: remove temporary filter when Hive Schema management code adds
    # handling of temporary things
    common_attribute_names = [
        x["name"] for x in common_attributes if not x.get("temporary")
    ]

    global_fields = [gen_wam_global_field(x) for x in common_attributes]

    field_groups = [gen_wam_field_group(x) for x in schema.field_groups]

    # NOTE: we only have 2 tables in the current setup
    tables = [
        gen_wam_table(schema, table_name)
        for table_name in ["fieldstats", "serverstats"]
    ]

    wam_schema = dict(
        enum_list=enums,
        alias_list=aliases,
        common_attribute_list=common_attribute_names,
        global_field_list=global_fields,
        field_list=fields,
        event_list=events,
        field_group_list=field_groups,
        table_list=tables,
    )

    json.dump(wam_schema, f, sort_keys=True, indent=4)


def gen_portable_schema(schema, output_dir):
    schema_json_path = os.path.join(output_dir, "wam_schema.json")
    with_open_file(schema_json_path, lambda f: gen_wam_schema(f, schema))
    return schema_json_path


def gen_client_schema(schema, **kvargs):
    return gen_schema_common(schema, **kvargs)


def get_doc(x):
    return x.get("doc", "")


def split_pars(s):
    return s.split("\n\n")


def format_erlang_comment(s, indent=""):
    if s == "":
        return ""
    if isinstance(indent, int):
        indent = " " * indent

    def format_par(s):
        wrapper = textwrap.TextWrapper(
            initial_indent=indent + "% ", subsequent_indent=indent + "% ", width=120
        )
        return wrapper.fill(s) + "\n"

    return (indent + "%\n").join(format_par(x) for x in split_pars(s))


def format_data_type(value, enum_prefix="", include_units=True):
    data_type = value["data_type"]
    if data_type == "enum":
        data_type = "enum " + enum_prefix + value["type"]

    units = ""
    if include_units and value["type"] == "timer":
        units = ", milliseconds"

    data_type += units

    return data_type


def gen_erlang_value_code(value, is_event=False):
    code = gen_value_code(value)

    flags = 0

    data_type = value["data_type"]
    if data_type == "float":
        flags |= 1
    elif data_type == "string":
        flags |= 2
    else:
        # everything else (bool, int, enum) or end-of-event markers
        # represented as integers, type code for which is 0
        pass

    if is_event:
        flags |= 4

    code |= flags << 24

    return str(code)


def gen_erlang_event_code(event):
    code = gen_event_code(event)

    flags = 4
    code |= flags << 24

    return str(code)


def gen_erlang_stubs(
    f, schema, properties=[], remove_server_side=True, generate_code_constants=False
):
    schema = gen_schema_common(
        schema, properties=properties, remove_server_side=remove_server_side
    )

    file_header = """\
% this file was \x40generated by wamc - WhatsApp application metrics compiler
\n
"""
    file_footer = """
"""
    f.write(file_header)

    # format enum constant definition
    def format_enum_const(id, code):
        return (
            "-ifndef("
            + id.upper()
            + ").\n"
            + "-define("
            + id.upper()
            + ", "
            + str(code)
            + ").\n"
            + "-endif.\n\n"
        )

    code_constant_defs = []

    # generate event definitions
    for event in schema.events:
        comment = get_doc(event)
        f.write(format_erlang_comment(comment))

        event_name = "wam_event_" + event["name"]
        event_name = event.get("erlang_name", event_name)

        f.write("-ifndef(__EVENT_" + event_name.upper() + "__).\n")
        f.write("-define(__EVENT_" + event_name.upper() + "__, 1).\n")
        f.write("-record(" + event_name + ", {\n")  # start record

        # merge fields and attributes (if any)
        fields = event.get("field", [])

        # generate fields code
        field_defs = []

        for field in fields:
            name = field["name"]
            value = field["value_def"]
            comment = "(" + format_data_type(value) + ") " + get_doc(value)
            indent = 4
            elem = format_erlang_comment(comment, indent=indent) + "    " + name
            field_defs.append(elem)

        # (optional) generate constants for events and fields
        if generate_code_constants:
            code_constant_defs.append("\n")
            code_constant_defs.append(
                format_enum_const(event_name, gen_event_code(event))
            )
            for field in fields:
                code_constant_defs.append(
                    format_enum_const(
                        "wam_field_" + event["name"] + "__" + field["name"],
                        field["field_code"],
                    )
                )

        # generate fields metadata
        field_codes = []
        for field in fields:
            value = field["value_def"]
            field_codes.append(gen_erlang_value_code(value))

        v2_code = gen_erlang_event_code(event)  # v2 code for event marker
        v1_code = "'undefined'"  # no longer used

        meta = "{" + v1_code + "," + v2_code + ",{" + ",".join(field_codes) + "}}"
        field_defs.insert(0, "    wam_meta = " + meta)

        f.write(",\n".join(field_defs))
        f.write("\n}).\n")  # end record
        f.write("-endif.  % __EVENT_" + event_name.upper() + "__\n\n")

    # generate enum definitions
    for enum in schema.enums:
        doc = get_doc(enum)
        comment = "enum " + enum["name"] + ": " + get_doc(enum)
        f.write(format_erlang_comment(comment))

        enum_id = "wam_enum_" + enum["name"]
        for c in enum["constant"]:
            doc = get_doc(c)
            elem = format_erlang_comment(doc) + format_enum_const(
                enum_id + "_" + c["name"], c["code"]
            )
            f.write(elem)

        if enum.get("erlang_gen_enum_descriptor"):
            descr = "["
            for i, c in enumerate(enum["constant"]):
                if i:
                    descr += ", "
                descr += "{" + c["name"] + ", " + str(c["code"]) + "}"
            descr += "]"
            enum_const = format_enum_const(enum_id, descr)
            f.write(enum_const)

        f.write("\n")

    if generate_code_constants:
        code_constant_defs.append("\n")
        for value in schema.values:
            code_constant_defs.append(
                format_enum_const("wam_value_" + value["name"], gen_value_code(value))
            )
        for x in code_constant_defs:
            f.write(x)
        f.write("\n")

    f.write(file_footer)


def gen_erlang_consts(
    f, schema, modname, hrl_filename, properties=[], remove_server_side=True
):

    schema = gen_schema_common(
        schema, properties=properties, remove_server_side=remove_server_side
    )

    file_header = (
        """\
% this file was \x40generated by wamc - WhatsApp application metrics compiler
-module("""
        + modname
        + """).
-include("""
        + '"'
        + hrl_filename
        + '"'
        + """).
-export([map/2]).

"""
    )
    f.write(file_header)

    def format_enum_map(enum_id, id, code):
        return "map(" + enum_id + ', <<"' + id + '">>) -> ?' + code.upper() + ";\n"

    for enum in schema.enums:
        doc = get_doc(enum)

        enum_id = "wam_enum_" + enum["name"]
        for c in enum["constant"]:
            doc = get_doc(c)
            elem = format_erlang_comment(doc) + format_enum_map(
                enum["name"], c["name"], enum_id + "_" + c["name"]
            )
            f.write(elem)
        f.write("\n\n\n")

    f.write("map(_, T) -> T.\n")


def gen_js_value(value, inEvent, code):
    name = snake_to_camelcase(value["name"])

    data_type = value["data_type"]
    type_name = value["type"]

    if type_name == "timer":
        js_type = "TIMER"
    elif data_type == "float":
        js_type = "NUMBER"
    elif data_type == "bool":
        js_type = "BOOLEAN"
    elif data_type == "enum":
        enum_name = value["type"]
        js_type = enum_name.upper()
    elif data_type == "string":
        js_type = "STRING"
    elif data_type == "int":
        js_type = "INTEGER"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False

    line = name + ": [" + str(code) + ", " + js_type + "],"

    if js_type == "TIMER" and inEvent:
        line += (
            " // mark"
            + snake_to_upper_camelcase(value["name"])
            + " created in defineEvent"
        )

    return line


def gen_js_type(value, inEvent):
    tab = "    "

    name = snake_to_camelcase(value["name"])
    pascalCaseName = snake_to_upper_camelcase(value["name"])

    data_type = value["data_type"]
    type_name = value["type"]

    if type_name == "timer":
        js_type = "number"
    elif data_type == "float":
        js_type = "number"
    elif data_type == "bool":
        js_type = "boolean"
    elif data_type == "enum":
        enum_name = value["type"]
        js_type = "$Values<typeof " + enum_name.upper() + ">"
    elif data_type == "string":
        js_type = "string"
    elif data_type == "int":
        js_type = "number"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False

    line = name + ": " + js_type + ","

    if type_name == "timer" and inEvent:
        line += "\n{tab}mark{pascalCaseName}: (options?: {{ showInTimeline?: boolean }}) => void,".format(
            tab=tab, pascalCaseName=pascalCaseName
        )

    return line


# attributes that are not exposed to the user directly, and reported only by
# wam_client
def is_wam_client_attribute(value):
    return value["name"] in ["ts", "event_sequence_number"]


def gen_js(f, schema):
    subs = {}
    tab = "    "
    tab2 = tab + tab

    # Enums
    subs["ENUM_NAMES"] = []
    subs["ENUM_FLOW_TYPES"] = []
    lines = subs["ENUMS"] = []
    for enum in schema.enums:
        lines.append("")

        doc = get_doc(enum)
        if doc != "":
            lines.append("// " + doc)

        name = enum["name"].upper()
        subs["ENUM_NAMES"].append("    " + name + ",")
        subs["ENUM_FLOW_TYPES"].append("    " + name + ": typeof " + name + ",")

        lines.append("const " + name + " = Object.freeze({")
        for c in enum["constant"]:
            lines.append(tab + c["name"].upper() + ": " + str(c["code"]) + ",")
        lines.append("});")

    # Event Classes
    lines = subs["EVENT_CLASSES"] = []
    blacklist = set(["Call"])
    for event in schema.events:
        event_name = snake_to_camelcase(event["name"], True)
        lines.append("declare class " + event_name + " extends WamEvent {")

        if event_name in blacklist:
            lines.append(
                tab + "// Metric types for this class have been "
                "purposefully skipped by wamc"
            )
        else:
            for field in event["field"]:
                value = field["value_def"]
                lines.append(tab + gen_js_type(value, True))

        lines.append("}\n")

    # Event Types
    lines = subs["EVENT_TYPES"] = []
    for event in schema.events:
        event_name = snake_to_camelcase(event["name"], True)
        lines.append(tab + event_name + ": typeof " + event_name + ",")

    # Globals (attributes)
    lines = subs["GLOBALS"] = []
    for field in schema.common_attributes:
        value = field["value_def"]
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime
        code = gen_value_code(value)
        lines.append(tab + gen_js_value(value, False, code))
    lines.sort()

    # Events
    lines = subs["EVENTS"] = []
    first = True
    for event in schema.events:
        if not first:
            lines.append("")
        first = False

        event_name = snake_to_camelcase(event["name"], True)
        lines.append(tab + event_name + ": [" + str(gen_event_code(event)) + ", {")

        for field in event["field"]:
            value = field["value_def"]
            field_code = field["field_code"]
            lines.append(tab2 + gen_js_value(value, True, field_code))

        lines.append(tab + "},")

        # embed sampling spec
        set_platform = event.get("set_platform")
        sampling_spec_dict = set_platform.get("web", {})

        schema_sampling_spec = sampling_spec_dict.get("schema", None)
        event_sampling_spec = sampling_spec_dict.get("event", None)
        if event_sampling_spec:
            lines.append(
                tab
                + "["
                + str(event_sampling_spec["debug_weight"])
                + ", "
                + str(event_sampling_spec["beta_weight"])
                + ", "
                + str(event_sampling_spec["release_weight"])
                + "]"
            )
        elif schema_sampling_spec:
            lines.append(
                tab
                + "["
                + str(schema_sampling_spec["debug_weight"])
                + ", "
                + str(schema_sampling_spec["beta_weight"])
                + ", "
                + str(schema_sampling_spec["release_weight"])
                + "]"
            )
        else:
            print(
                "error: all the we events need a sampling spec defined, either at schema level or event level",
                file=sys.stderr,
            )

        lines.append(tab + "],")

    # Substitute In
    output = "// \x40generated by wamc - WhatsApp application metrics compiler\n"

    templateFile = open("webclient/webc-wamc-template.js", "r")
    output += templateFile.read()
    templateFile.close()

    for key in subs:
        marker = "// <-- AUTOGEN " + key + " -->"
        output = output.replace(marker, "\n".join(subs[key]))

    f.write(output)


def gen_kaios_meta_json(f, schema):
    meta_dict = {
        "dummy_field": "\x40generated",
        "events": {},
        "globals": {},
        "enums": {},
    }

    # Enums
    meta_dict["enums"]["$RAW_ARG_TYPE"] = {"INT": 0, "FLOAT": 3, "BOOL": 1, "STRING": 2}

    for enum in schema.enums:
        enum_upper = enum["name"].upper()
        enum_dict = meta_dict["enums"].setdefault(enum_upper, {})

        for const in enum["constant"]:
            if const["deprecated"]:
                continue

            const_upper = const["name"].upper()
            enum_dict[const_upper] = const["code"]

    # Events
    def get_field_type_code(value):
        # These values are from common/wam/wam.js file in KaiOS client repository
        type_name_to_code = {
            "timer": 0,  # integer
            "float": 3,
            "bool": 1,
            "enum": 0,  # integer
            "string": 2,
            "int": 0,
        }

        code = type_name_to_code.get(value["data_type"])
        assert code is not None, "Unknown type " + str(value["data_type"])
        return code

    for event in schema.events:
        if event["deprecated"]:
            continue

        event_name = snake_to_camelcase(event["name"], capitalize_first=True)
        event_dict = meta_dict["events"].setdefault(event_name, {})
        event_dict["id"] = gen_event_code(event)
        event_dict["fields"] = {}

        for field in event["field"]:
            if field["deprecated"]:
                continue

            field_name_camelcase = snake_to_camelcase(
                field["name"], capitalize_first=False
            )
            field_code = field["field_code"]
            field_type = get_field_type_code(field["value_def"])

            event_dict["fields"][field_name_camelcase] = [field_code, field_type]

    # Globals
    for field in schema.common_attributes:
        value = field["value_def"]
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime
        code = gen_value_code(value)
        type_ = get_field_type_code(value)

        field_name_camelcase = snake_to_camelcase(field["name"], capitalize_first=False)
        meta_dict["globals"][field_name_camelcase] = [code, type_]

    json.dump(meta_dict, f, indent=4)


def gen_kaios_js(f, schema):
    # Header
    f.write("// @flow strict\n")
    f.write("// \x40generated by wamc compiler\n\n")

    f.write("// These are just typed stubs, function calls are replaced at compile\n")
    f.write("// time with WAM (WhatsApp Metrics) runtime calls and enum values are\n")
    f.write("// replaced with numeric values.\n\n")

    f.write("opaque type Enum<Name: string> = number;\n\n")

    f.write("type $RAW_ARG_TYPE = {\n")
    f.write(" " * 4 + "INT: Enum<'$RAW_ARG_TYPE'>,\n")
    f.write(" " * 4 + "BOOL: Enum<'$RAW_ARG_TYPE'>,\n")
    f.write(" " * 4 + "STRING: Enum<'$RAW_ARG_TYPE'>,\n")
    f.write(" " * 4 + "FLOAT: Enum<'$RAW_ARG_TYPE'>,\n")
    f.write("};\n\n")

    f.write("type RawArgs = Array<\n")
    f.write(
        " " * 4 + "[number, Enum<'$RAW_ARG_TYPE'>, number | string | boolean | null]\n"
    )
    f.write(">;\n\n")

    # Enums
    for enum in schema.enums:
        enum_upper = enum["name"].upper()
        f.write("type " + enum_upper + " = {\n")

        for const in enum["constant"]:
            if const["deprecated"]:
                continue

            const_upper = const["name"].upper()
            f.write(" " * 4 + "{}: Enum<'{}'>,\n".format(const_upper, enum_upper))

        f.write("};\n\n")

    # Events
    def format_value_type(value):
        type_name_to_js_type = {
            "timer": "number",
            "float": "number",
            "bool": "boolean",
            "enum": "Enum<'" + value["type"].upper() + "'>",
            "string": "string",
            "int": "number",
        }

        str_ = type_name_to_js_type.get(value["data_type"])
        assert str_ is not None, "Unknown type " + str(value["data_type"])
        return "?" + str_ + ",\n"

    # Argument types for each event
    for event in schema.events:
        if event["deprecated"]:
            continue

        event_name = snake_to_camelcase(event["name"], capitalize_first=True)
        args_type_name = event_name + "Metric"

        field_lines = []
        for field in event["field"]:
            if field["deprecated"]:
                continue

            field_name_camelcase = snake_to_camelcase(
                field["name"], capitalize_first=False
            )
            if "doc" in field:
                field_doc = "\n    // ".join(d for d in field["doc"].splitlines() if d)
                field_lines.append(f"// {field_doc} \n")
            field_lines.append(
                field_name_camelcase + ": " + format_value_type(field["value_def"])
            )

        if "doc" in event and event["doc"]:
            event_doc = "\n    ".join((d for d in event["doc"].splitlines() if d))
            f.write(f"/*\n    Doc: {args_type_name}\n")
            f.write(f"    {event_doc}")
            f.write("\n*/\n")

        if field_lines:
            f.write("type {} = $Shape<{{\n".format(args_type_name))
            for field_line in field_lines:
                f.write(" " * 4 + field_line)
            f.write("}>;\n\n")
        else:
            f.write("type {} = $Shape<{{}}>;\n\n".format(args_type_name))

    f.write("type EventFunction<A, T> = {\n")
    f.write(" " * 4 + "(args: A, rawArgs?: RawArgs): T,\n")
    f.write(
        " " * 4
        + "sampleEvery: (sampleRate: number, getArgs: () => A, getRawArgs?: () => RawArgs) => T\n"
    )
    f.write("};\n")

    f.write("declare class WaMetricsBase<T> {\n")
    f.write(" " * 4 + "$RAW_ARG_TYPE: $RAW_ARG_TYPE;\n")
    for enum in schema.enums:
        enum_upper = enum["name"].upper()
        f.write(" " * 4 + enum_upper + ": " + enum_upper + ";\n")

    f.write("\n")

    for event in schema.events:
        if event["deprecated"]:
            continue

        event_name = snake_to_camelcase(event["name"], capitalize_first=True)
        args_type_name = event_name + "Metric"
        f.write(
            " " * 4 + "{}: EventFunction<{}, T>;\n".format(event_name, args_type_name)
        )

    f.write("\n")

    # Globals
    global_field_lines = []
    for field in schema.common_attributes:
        if field["deprecated"]:
            continue

        value = field["value_def"]
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime

        field_name_camelcase = snake_to_camelcase(field["name"], capitalize_first=False)
        global_field_lines.append(
            field_name_camelcase + "?: " + format_value_type(value)
        )

    if global_field_lines:
        f.write(" " * 4 + "updateAttributes: (args: {\n")
        for field_line in global_field_lines:
            f.write(" " * 8 + field_line)
        f.write(" " * 4 + "}) => T;\n")
    else:
        f.write(" " * 4 + "updateAttributes: (args: {}) => T;\n")

    f.write("}\n\n")

    f.write("declare class WaMetrics extends WaMetricsBase<void> {\n")
    f.write("    async: WaMetricsBase<Promise<void>>;\n")
    f.write("}\n\n")

    f.write("declare var WA_METRICS: WaMetrics;\n")


def format_c_comment(s, indent="", comment_open="/*"):
    if s == "":
        return ""
    if isinstance(indent, int):
        indent = " " * indent
    wrapper = textwrap.TextWrapper(
        initial_indent=indent + comment_open + " ",
        subsequent_indent=indent + " * ",
        width=60,
    )
    return wrapper.fill(s + " */") + "\n"


def gen_c_enums(f, schema):
    # format enum constant definition
    def format_enum_const(id, code):
        return "    " + id.upper() + " = " + str(code) + ",\n"

    # generate enum definitions
    for enum in schema.enums:
        f.write(format_c_comment(get_doc(enum)))

        enum_id = "wam_enum_" + enum["name"]
        f.write("enum " + enum_id + " {\n")

        for c in enum["constant"]:
            f.write(format_c_comment(get_doc(c), indent=4))

            elem = format_enum_const(enum_id + "_" + c["name"], c["code"])
            f.write(elem)
        f.write("};\n\n")


# special constants for wam_common.c/wam_runtime.c (wam C runtime)
def gen_c_runtime_constants(f, schema):
    f.write(
        """\n
/* these are only used when included in wam_common.c/wam_runtime.c */
#if defined(__WAM_COMMON_C__) || defined(__WAM_RUNTIME_C__)\n
"""
    )

    attributes = [x["value_def"] for x in schema.common_attributes]
    wam_client_attributes = [x for x in attributes if is_wam_client_attribute(x)]

    # generate codes for special attributes for wam runtime
    for value in wam_client_attributes:
        f.write(
            "#define WAM_ATTRIBUTE_%s %d\n" % (value["name"].upper(), value["offset"])
        )

    # array of valid attribute codes, also a mapping from attribute code to
    # internal index (offset)
    f.write("\n" "static\n" "int wam_attribute_codes[] = {")

    # place attributes in the array according to their offsets
    ordered_attributes = sorted(attributes, key=lambda x: x["offset"])
    for offset, value in enumerate(ordered_attributes):
        assert offset == value["offset"]

        if offset % 10 == 0:
            f.write("\n    ")
        f.write("%d, " % gen_value_code(value))
    f.write("\n};\n\n")

    f.write("\n#endif  /* #ifdef __WAM_COMMON_C__ */\n")


def assign_attribute_offsets(attributes):
    # preorder attributes by codes so that we could generate bsearch'able
    # metadata for them -- see gen_c_runtime_constants() above for details
    ordered_attributes = sorted(attributes, key=lambda x: gen_value_code(x))

    # assign 'offset' for each attribute
    for offset, attr in enumerate(ordered_attributes):
        attr["offset"] = offset


def gen_c_type(value):
    data_type = value["data_type"]
    type_name = value["type"]

    if data_type == "string":
        attr_kind = "string"
        ctype = "const char *"
    elif data_type == "enum":
        ctype = "enum wam_enum_" + type_name + " "
        attr_kind = "numeric"
    elif data_type == "bool":
        ctype = "bool "
        attr_kind = "numeric"
    elif data_type == "int":
        ctype = "int64_t "
        attr_kind = "numeric"
    elif data_type == "float":
        ctype = "double "
        attr_kind = "numeric"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False
    return ctype, attr_kind


def gen_c_h(f, schema, schema_version):
    file_header = """\
/* this file was \x40generated by wamc - WhatsApp application metrics compiler */
#ifndef __WAM_STUBS_H__
#define __WAM_STUBS_H__\n\n
"""
    file_footer = """
#endif  /* __WAM_STUBS_H__ */
"""
    f.write(file_header)

    f.write("#define WAM_C_SCHEMA_VERSION_%s\n\n\n" % schema_version)

    # make sure nothing else gets pulled when included in ObjectiveC sources;
    # ObjC code should use WamStubs.h instead
    f.write("#ifndef __OBJC__\n\n\n")

    gen_c_enums(f, schema)

    attributes = [x["value_def"] for x in schema.common_attributes]
    assign_attribute_offsets(attributes)

    for value in attributes:
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime

        doc = get_doc(value)
        f.write(format_c_comment(doc))

        attr_id = value["name"]
        offset = value["offset"]

        ctype, attr_kind = gen_c_type(value)

        f.write("#ifdef CHANNEL_SUPPORT\n")

        to_set_channel_args = ["CHANNEL_REGULAR", "CHANNEL_REALTIME"]
        if value["enabled_for_anonymous"]:
            to_set_channel_args.append("CHANNEL_PRIVATE")

        # Set to value
        f.write("static inline void wam_set_%s(%svalue) {\n" % (attr_id, ctype))
        for channel_arg in to_set_channel_args:
            f.write(
                "    wam_channel_set_%s_attribute(%s, %d, value);\n"
                % (attr_kind, channel_arg, offset)
            )
        f.write("}\n")

        # Set to null
        f.write("static inline void wam_set_%s_to_null(void) {\n" % attr_id)
        for channel_arg in to_set_channel_args:
            f.write(
                "    wam_channel_set_attribute_to_null_impl(%s, %d);\n"
                % (channel_arg, offset)
            )
        f.write("}\n")

        f.write("#else\n")

        # Set to value
        f.write("static inline void wam_set_%s(%svalue) {\n" % (attr_id, ctype))
        f.write("    wam_set_%s_attribute(%d, value);\n" % (attr_kind, offset))
        f.write("}\n")

        # Set to null
        f.write("static inline void wam_set_%s_to_null(void) {\n" % attr_id)
        f.write("    wam_set_attribute_to_null_impl(%d);\n" % offset)
        f.write("}\n")

        f.write("#endif\n")

        f.write("\n")

        # XXX: support old_name?
        # old_name = x.get('old_name')
        # if old_name:
    f.write("\n")

    # generate event definitions
    for event in schema.events:
        comment = get_doc(event)

        f.write("\n")
        f.write(format_c_comment(comment))

        f.write("\n#endif  /* #ifndef __OBJC__ */\n\n\n")

        event_code = gen_event_code(event)
        event_id = event["name"]
        f.write("struct wam_event_" + event_id + " {\n")

        event_fields = event.get("field", [])

        if event_fields == []:
            # empty structs are not allowed in C, even if they are, they are
            # incompatible with C++, so adding a dummy field to make struct size
            # explicitly non-0
            f.write("    int empty;\n")

        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]
            comment = (
                "("
                + format_data_type(value, enum_prefix="wam_enum_")
                + ") "
                + get_doc(value)
            )
            f.write(format_c_comment(comment, indent=4))
            if value["data_type"] == "string":
                ctype = "const char *"
            else:
                ctype = "double "
            elem = "    %s%s;\n" % (ctype, field_id)
            f.write(elem)

        f.write("};\n")

        f.write("\n\n#ifndef __OBJC__\n\n")

        # generate event reset
        f.write(
            "static inline void wam_reset_%s(struct wam_event_%s *e) {\n"
            % (event_id, event_id)
        )

        # quick method for setting all numeric fields to wam_numeric_null(), i.e. 0xff..0xff -- a specially encoded NaN
        if event_fields:
            f.write("    memset(e, 0xff, sizeof(*e));\n")

            for field in event_fields:
                field_id = field["name"]
                value = field["value_def"]

                if value["data_type"] == "string":
                    f.write("    e->%s = 0;\n" % field_id)
        else:
            f.write("    (void)e;\n")

        f.write("}\n")

        # generate event fields serializer
        field_serializer_name = ""
        if event_fields:
            field_serializer_name = "wam_serialize_%s_fields" % event_id
            f.write(
                "static inline void %s(struct wam_event_%s *e) {\n"
                % (field_serializer_name, event_id)
            )
            for field in event_fields:
                field_id = field["name"]
                value = field["value_def"]
                field_code = field["field_code"]
                if value["data_type"] == "string":
                    field_kind = "string"
                else:
                    field_kind = "numeric"
                f.write(
                    "    wam_maybe_serialize_%s_field(%d, e->%s);\n"
                    % (field_kind, field_code, field_id)
                )
            f.write("}\n")

        # generate event code macro
        f.write("\n")
        f.write("#define WAM_EVENT_CODE_%s %d" % (event_id, event_code))
        f.write("\n")

        # generate field_code macros
        f.write("\n")
        if event_fields:
            for field in event_fields:
                field_id = field["name"]
                value = field["value_def"]
                field_code = field["field_code"]
                f.write(
                    "#define WAM_FIELD_CODE_%s_%s  %d\n"
                    % (event_id, field_id, field_code)
                )
        f.write("\n")

        # generate event logger
        f.write(
            "static inline void wam_log_%s(struct wam_event_%s *e, int weight) {\n"
            % (event_id, event_id)
        )

        field_serializer = "0"
        if field_serializer_name:
            field_serializer = "&" + field_serializer_name

        if event["realtime"]:
            channel_arg = "CHANNEL_REALTIME"
        elif event["anonymous"]:
            channel_arg = "CHANNEL_PRIVATE"
        else:
            channel_arg = "CHANNEL_REGULAR"

        f.write("#ifdef CHANNEL_SUPPORT\n")

        f.write(
            "    wam_channel_log_event_impl(%d, weight, e, (void (*)(void *))%s, %s);\n"
            % (event_code, field_serializer, channel_arg)
        )

        f.write("#elif REALTIME_SUPPORT\n")

        if event["realtime"]:
            f.write(
                "    wam_log_event_impl(%d, weight, e, (void (*)(void *))%s, %s);\n"
                % (event_code, field_serializer, "true")
            )
        else:
            f.write(
                "    wam_log_event_impl(%d, weight, e, (void (*)(void *))%s, %s);\n"
                % (event_code, field_serializer, "false")
            )

        f.write("#else\n")
        f.write(
            "    wam_log_event_impl(%d, weight, e, (void (*)(void *))%s);\n"
            % (event_code, field_serializer)
        )
        f.write("#endif\n")

        f.write("};\n")

    gen_c_runtime_constants(f, schema)

    f.write("\n#endif  /* #ifndef __OBJC__ */\n")

    f.write(file_footer)


def gen_wamsys_channel_string(event):
    if event["realtime"]:
        channel = "1 /* realtime channel */"
    elif event["anonymous"]:
        channel = "2 /* private channel */"
    else:
        channel = "0 /* regular channel */"
    return channel


def get_wamsys_sampling_rates(event, platform):
    if "set_platform" in event and platform in event["set_platform"]:
        sampling_spec_dict = event["set_platform"][platform]
        schema_sampling_spec = sampling_spec_dict.get("schema", None)
        event_sampling_spec = sampling_spec_dict.get("event", None)
        if event_sampling_spec:
            debug = event_sampling_spec["debug_weight"]
            beta = event_sampling_spec["beta_weight"]
            release = event_sampling_spec["release_weight"]
        elif schema_sampling_spec:
            debug = schema_sampling_spec["debug_weight"]
            beta = schema_sampling_spec["beta_weight"]
            release = schema_sampling_spec["release_weight"]
        else:
            print(
                "error: all %s events needs a sampling spec defined, either at schema level or event level"
                % (platform),
                file=sys.stderr,
            )
    else:
        print(
            "error: all %s event needs a sampling spec defined, either at schema level or event level"
            % (platform),
            file=sys.stderr,
        )

    return debug, beta, release


def gen_wamsys_wa_impl(f, schema, schema_version, platform):
    file_header = """\
// GENERATED CODE - DO NOT EDIT
//
// This file was \x40generated by wamc - WhatsApp field metrics compiler

"""
    f.write(file_header)

    f.write("#include <WhatsAppMetrics/WAMStubsInterfaces.h>\n" "#include <string.h>\n")

    if platform == "stubs":
        f.write("#include <WhatsAppCoreFoundation/WCFBase.h>\n")
    else:
        f.write(
            "#include <MessengerCoreFoundation/MCFData.h>\n"
            '#include "wam/WAMFieldstats.h"\n'
            '#include "wam/wam_serialize.h"\n'
        )

    f.write(
        "#ifndef WAM_C_SCHEMA_VERSION_%s\n"
        '#error "mismatch between C and H file schema versions, PLEASE COPY *ALL* FILES FROM fieldstats/wamsys/"\n'
        "#endif\n\n" % schema_version
    )

    # generate event definitions
    for event in schema.events:
        comment = get_doc(event)

        f.write("\n")
        f.write(format_c_comment(comment))

        event_code = gen_event_code(event)
        event_id = event["name"]
        event_fields = event.get("field", [])
        event_channel = gen_wamsys_channel_string(event)

        # generate event reset
        f.write("void wam_reset_%s(struct wam_event_%s *e) {\n" % (event_id, event_id))
        # quick method for setting all numeric fields to wam_numeric_null(),
        # i.e. 0xff..0xff -- a specially encoded NaN
        if event_fields:
            f.write("    memset(e, 0xff, sizeof(*e));\n")

            for field in event_fields:
                field_id = field["name"]
                value = field["value_def"]

                if value["data_type"] == "string":
                    f.write("    e->%s = 0;\n" % field_id)
        else:
            f.write("    (void)e;\n")
        f.write("}\n\n")

        # generate serialization function

        # function header
        f.write("void wam_log_%s(struct wam_event_%s *e) {\n" % (event_id, event_id))

        if platform == "stubs":
            # Mark is as WCF_UNUSED_PARAM
            f.write("    WCF_UNUSED_PARAM(e);\n")

        else:
            # serial buffer initialization
            f.write(
                "    /* Initialize serial buffer */\n"
                "    serial_buf_t sbuf;\n"
                "    serial_buf_init(&sbuf);\n"
                "\n"
            )
            # serialize fields to serial buffer
            f.write("    /* Serialize event fields to serial buffer */\n")
            if event_fields:
                for field in event_fields:
                    field_id = field["name"]
                    value = field["value_def"]
                    field_code = field["field_code"]
                    if value["data_type"] == "string":
                        field_kind = "string"
                    else:
                        field_kind = "numeric"
                    if field_id == "is_from_wamsys":
                        # Hard code the value of the `is_from_wamsys` field to `true`
                        f.write(
                            "    wam_maybe_serialize_%s_field_to_serial_buf(&sbuf, %d, true);\n"
                            % (field_kind, field_code)
                        )
                    else:
                        f.write(
                            "    wam_maybe_serialize_%s_field_to_serial_buf(&sbuf, %d, e->%s);\n"
                            % (field_kind, field_code, field_id)
                        )
            f.write("\n")

            # log serialized event
            debug_rate, beta_rate, release_rate = get_wamsys_sampling_rates(
                event, platform
            )
            f.write(
                "    /* Convert serial buffer to MCFDataRef and log to the app */\n"
                "    MCFDataRef serializedEvent = MCFDataCreate((const unsigned char *) sbuf.data, (int32_t) sbuf.size);\n"
                "    WAMFieldstatsLogEvent(%s, serializedEvent, %s, %s, %s, %s);\n"
                "    MCFRelease(serializedEvent);\n"
                "\n" % (event_code, event_channel, debug_rate, beta_rate, release_rate)
            )

            # free serial buffer
            f.write("    /* Free serial buffer */\n" "    serial_buf_free(&sbuf);\n")

        f.write("}\n\n")


def gen_wamsys_interface(f, schema, schema_version):

    file_header = """\
/* this file was \x40generated by wamc - WhatsApp application metrics compiler */
#ifndef __WAM_STUBS_INTERFACE_H__
#define __WAM_STUBS_INTERFACE_H__\n\n
"""
    file_footer = """
#endif  /* __WAM_STUBS_INTERFACE_H__ */
"""
    f.write(file_header)

    f.write("#define WAM_C_SCHEMA_VERSION_%s\n\n\n" % schema_version)

    gen_c_enums(f, schema)

    # generate event definitions
    for event in schema.events:
        comment = get_doc(event)

        f.write("\n")
        f.write(format_c_comment(comment))

        event_code = gen_event_code(event)
        event_id = event["name"]
        f.write("struct wam_event_" + event_id + " {\n")

        event_fields = event.get("field", [])

        if event_fields == []:
            # empty structs are not allowed in C, even if they are, they are
            # incompatible with C++, so adding a dummy field to make struct size
            # explicitly non-0
            f.write("    int empty;\n")

        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]
            comment = (
                "("
                + format_data_type(value, enum_prefix="wam_enum_")
                + ") "
                + get_doc(value)
            )
            f.write(format_c_comment(comment, indent=4))
            if value["data_type"] == "string":
                ctype = "const char *"
            else:
                ctype = "double "
            elem = "    %s%s;\n" % (ctype, field_id)
            f.write(elem)

        f.write("};\n\n")

        # generate event reset  declaration
        f.write("void wam_reset_%s(struct wam_event_%s *e); \n" % (event_id, event_id))
        # generate event logger declaration
        f.write("void wam_log_%s(struct wam_event_%s *e); \n" % (event_id, event_id))

    f.write(file_footer)


def gen_objc_enums(f, schema):
    # format enum constant definition
    def format_enum_const(id, code):
        return "    " + id.upper() + " = " + str(code) + ",\n"

    # generate enum definitions
    for enum in schema.enums:
        f.write(format_c_comment(get_doc(enum)))

        enum_id = "wam_enum_" + enum["name"]
        f.write("typedef NS_ENUM(NSInteger, %s) {\n" % enum_id)

        for c in enum["constant"]:
            f.write(format_c_comment(get_doc(c), indent=4))

            elem = format_enum_const(enum_id + "_" + c["name"], c["code"])
            f.write(elem)
        f.write("};\n\n")


def gen_objc_type(value, nullability=None):
    data_type = value["data_type"]
    type_name = value["type"]

    if data_type == "string":
        attr_kind = "string"
        if nullability is None:
            objc_type = "NSString *"
        else:
            objc_type = "NSString *" + " " + nullability + " "
    elif data_type == "enum":
        objc_type = "wam_enum_" + type_name + " "
        attr_kind = "numeric"
    elif data_type == "bool":
        objc_type = "BOOL "
        attr_kind = "numeric"
    elif data_type == "int":
        objc_type = "int64_t "
        attr_kind = "numeric"
    elif data_type == "float":
        objc_type = "double "
        attr_kind = "numeric"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False
    return objc_type, attr_kind


# generate attribute and event serializers
def gen_objc_h(f, schema):
    file_header = """\
// GENERATED CODE - DO NOT EDIT
//
// This file was \x40generated by wamc - WhatsApp application metrics compiler

#ifndef __WamStubs_H__
#define __WamStubs_H__

NS_ASSUME_NONNULL_BEGIN\n
"""
    file_footer = """NS_ASSUME_NONNULL_END

#endif  /* __WamStubs_H__ */

// ex: ft=objc
"""

    f.write(file_header)

    gen_objc_enums(f, schema)

    # generate attributes
    attributes = [x["value_def"] for x in schema.common_attributes]
    assign_attribute_offsets(attributes)

    for value in attributes:
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime

        f.write(format_c_comment(get_doc(value)))

        attr_id = value["name"]
        objc_type, attr_kind = gen_objc_type(value, nullability="_Nullable")

        f.write("extern void wam_set_%s(%svalue);\n" % (attr_id, objc_type))
        f.write("extern void wam_set_%s_to_null(void);\n\n" % attr_id)

    # add WamProtobufSerializable protocol
    protobuf_serializable_protocol = """\
@protocol WamProtobufSerializable

- (BOOL)containsStringForKey:(int64_t)key;
- (void)setString:(NSString *)stringValue forKey:(int64_t)key;
- (NSString *)stringForKey:(int64_t)key;

- (BOOL)containsIntegerForKey:(int64_t)key;
- (void)setInteger:(int64_t)integerValue forKey:(int64_t)key;
- (int64_t)integerForKey:(int64_t)key;

- (BOOL)containsDoubleForKey:(int64_t)key;
- (void)setDouble:(double)doubleValue forKey:(int64_t)key;
- (double)doubleForKey:(int64_t)key;

@end\n
"""
    f.write(protobuf_serializable_protocol)

    # generate event definitions
    for event in schema.events:
        f.write(format_c_comment(get_doc(event)))

        event_id = snake_to_upper_camelcase(event["name"])
        gen_objc_serialization = "gen_objc_serialization" in event.get("tags", [])
        f.write("@interface WamEvent%s : WamEvent\n" % event_id)
        f.write("- (instancetype)init NS_DESIGNATED_INITIALIZER;\n")
        f.write(
            "- (instancetype)initWithCode:(int)code weight:(int)weight NS_DESIGNATED_INITIALIZER NS_UNAVAILABLE;\n"
        )
        if gen_objc_serialization:
            f.write(
                "- (instancetype)initWithProtobufCoder:(id<WamProtobufSerializable>)coder;\n"
            )
            f.write(
                "- (void)encodeWithProtobufCoder:(id<WamProtobufSerializable>)coder;\n"
            )
        event_fields = event.get("field", [])
        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]
            comment = (
                "("
                + format_data_type(value, enum_prefix="wam_enum_", include_units=False)
                + ") "
                + get_doc(value)
            )
            f.write(format_c_comment(comment, indent=0))

            objc_type, attr_kind = gen_objc_type(value)
            if value["data_type"] == "string":
                objc_property = "@property (nullable, nonatomic, copy) NSString *"
            elif value["data_type"] == "enum":
                objc_property = "@property (nonatomic, assign) %s" % objc_type
            else:
                objc_property = "@property (nonatomic, assign) double "

            # NOTE: timer fields can be reported using either seconds or
            # milliseconds as units
            #
            # this is reflected in property names which have units ('_seconds'
            # or '_milliseconds') as a suffix
            #
            # in fieldstats v1 on iphone, timer values used to be reported in
            # seconds (in contrast to other platforms which used millisecond as
            # a unit) which caused whole lot of confusion, errors and need for
            # manual maintenance
            #
            # to prevent further instrumentation errors we include expicit
            # measurement units in the name of each field
            #
            # XXX: we may consider adding such unix suffixes other platforms as
            # well
            if value["type"] == "timer":
                # this is the actual property backed by an instance variable
                f.write("%s%s;\n" % (objc_property, field_id + "_milliseconds"))
                # this will be accessed through custom setters and getters
                f.write("%s%s;\n" % (objc_property, field_id + "_seconds"))
            else:
                f.write("%s%s;\n" % (objc_property, field_id))
                if value["data_type"] == "enum":
                    f.write("- (BOOL)is_%s_set;\n" % field_id)

        f.write("@end\n\n")  # event

    f.write(file_footer)


def gen_weight_consts(f, schema):
    weights_list = []
    for event in schema.events:
        event_name = snake_to_upper_camelcase(event["name"])
        set_platform = event.get("set_platform")
        sampling_spec_dict = set_platform.get("iphone", {})

        schema_sampling_spec = sampling_spec_dict.get("schema", None)
        event_sampling_spec = sampling_spec_dict.get("event", None)
        if event_sampling_spec:
            weights_list.append(
                [
                    event_name,
                    event_sampling_spec["debug_weight"],
                    event_sampling_spec["beta_weight"],
                    event_sampling_spec["release_weight"],
                ]
            )
        elif schema_sampling_spec:
            weights_list.append(
                [
                    event_name,
                    schema_sampling_spec["debug_weight"],
                    schema_sampling_spec["beta_weight"],
                    schema_sampling_spec["release_weight"],
                ]
            )
        else:
            print(
                "error: all the iphone events need a sampling spec defined, either at schema level or event level",
                file=sys.stderr,
            )

    f.write("# if DEBUG\n")
    for weights in weights_list:
        f.write(
            "static const int Wam%sSamplingWeight = %d;\n" % (weights[0], weights[1])
        )
    f.write("# elif BETA\n")
    for weights in weights_list:
        f.write(
            "static const int Wam%sSamplingWeight = %d;\n" % (weights[0], weights[2])
        )
    f.write("# elif APP_STORE\n")
    for weights in weights_list:
        f.write(
            "static const int Wam%sSamplingWeight = %d;\n" % (weights[0], weights[3])
        )
    f.write("# else\n")
    for weights in weights_list:
        # in case anyone changes code manually and no weight is generated
        f.write("static const int Wam%sSamplingWeight = %d;\n" % (weights[0], 1))

    f.write("# endif\n\n")


def gen_objc_m(f, schema, schema_version):
    file_header = """\
// GENERATED CODE - DO NOT EDIT
//
// This file was \x40generated by wamc - WhatsApp field metrics compiler

#import "Wam.h"
#import "WAStackTrace.h"\n\n
"""
    f.write(file_header)

    f.write(
        '#include "wam_stubs.h"\n'
        "#ifndef WAM_C_SCHEMA_VERSION_%s\n"
        '#error "mismatch between C and ObjC schema versions, PLEASE COPY *ALL* FILES FROM fieldstats/iphone/"\n'
        "#endif\n\n"
        'NSString *const WAMEnumAccessViolationError = @"accessing not initialized enum value";\n\n'
        % schema_version
    )

    gen_weight_consts(f, schema)

    # generate attributes
    attributes = [x["value_def"] for x in schema.common_attributes]

    for value in attributes:
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime

        attr_id = value["name"]
        offset = value["offset"]
        objc_type, attr_kind = gen_objc_type(value, nullability="_Nullable")

        f.write("void wam_set_%s(%svalue) {" % (attr_id, objc_type))
        f.write(" WAM_SET_%s_ATTRIBUTE(%d, value); " % (attr_kind.upper(), offset))
        f.write("}\n")

        f.write("void wam_set_%s_to_null(void) {" % attr_id)
        f.write(" WAM_SET_ATTRIBUTE_TO_NULL(%d); " % offset)
        f.write("}\n\n")

    # generate ObjC classes implementation
    for event in schema.events:
        event_id = snake_to_upper_camelcase(event["name"])
        event_code = gen_event_code(event)

        event_fields = event.get("field", [])
        gen_objc_serialization = "gen_objc_serialization" in event.get("tags", [])

        f.write("\n")
        f.write("@implementation WamEvent%s" % event_id)

        ivar_definitions = ""
        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]

            if value["data_type"] == "enum":
                # enum values will be backed up by NSNumber * to distinguish
                # 0 values from not defined ones
                ivar_definitions += "    NSNumber *_%s_number;\n" % field_id

        if len(ivar_definitions) > 0:
            f.write(" {\n%s}" % ivar_definitions)

        f.write("\n")

        # generate init function
        f.write("- (instancetype)init {\n")
        f.write(
            "    self = [super initWithCode:%d weight:Wam%sSamplingWeight];\n"
            % (event_code, snake_to_upper_camelcase(event["name"]))
        )
        f.write("    return self;\n")
        f.write("}\n")

        if gen_objc_serialization:
            # generate initWithCoder function
            f.write(
                "- (instancetype)initWithProtobufCoder:(id<WamProtobufSerializable>)coder {\n"
            )
            f.write("    self = [self init];\n")
            f.write("    if (self) {\n")
            for field in event_fields:
                field_id = field["name"]
                value = field["value_def"]
                field_code = field["field_code"]
                if value["data_type"] == "string":
                    f.write(
                        "        if ([coder containsStringForKey:%d]) {\n" % field_code
                    )
                    f.write(
                        "            _%s = [coder stringForKey:%d];\n"
                        % (field_id, field_code)
                    )
                    f.write("        }\n")
                elif value["data_type"] == "enum":
                    f.write(
                        "        if ([coder containsIntegerForKey:%d]) {\n" % field_code
                    )
                    f.write(
                        "            _%s_number = @([coder integerForKey:%d]);\n"
                        % (field_id, field_code)
                    )
                    f.write("        }\n")
                else:
                    f.write(
                        "        if ([coder containsDoubleForKey:%d]) {\n" % field_code
                    )
                    f.write(
                        "            _%s = [coder doubleForKey:%d];\n"
                        % (field_id, field_code)
                    )
                    f.write("        }\n")
            f.write("    }\n")
            f.write("    return self;\n")
            f.write("}\n")

        # Supports logging to realtime, anonymous channels
        if event["realtime"]:
            channel_arg = "CHANNEL_REALTIME"
        elif event["anonymous"]:
            channel_arg = "CHANNEL_PRIVATE"
        else:
            channel_arg = "CHANNEL_REGULAR"
        f.write("- (channel_type_t)getChannel {\n")
        f.write("    return %s;\n" % channel_arg)
        f.write("}\n")

        # generate clear
        f.write("- (void)clear {\n")
        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]

            if value["data_type"] == "string":
                f.write("    _%s = nil;\n" % field_id)
            elif value["data_type"] == "enum":
                f.write("    _%s_number = nil;\n" % field_id)
            else:
                f.write("    _%s = wam_numeric_null();\n" % field_id)
        f.write("}\n")

        # generate copyWithZone
        f.write("- (instancetype)copyWithZone:(NSZone *)zone {\n")
        f.write("    WamEvent%s *copy = [WamEvent%s new];\n" % (event_id, event_id))
        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]
            if value["type"] == "timer":
                f.write(
                    "    copy.%s_milliseconds = self.%s_milliseconds;\n"
                    % (field_id, field_id)
                )
            elif value["data_type"] == "enum":
                f.write("    if (self.is_%s_set) {\n" % field_id)
                f.write("        copy.%s = self.%s;\n" % (field_id, field_id))
                f.write("    }\n")
            else:
                f.write("    copy.%s = self.%s;\n" % (field_id, field_id))
        f.write("    return copy;\n")
        f.write("}\n")

        if gen_objc_serialization:
            # generate encodeWithCoder
            f.write(
                "- (void)encodeWithProtobufCoder:(id<WamProtobufSerializable>)coder {\n"
            )
            for field in event_fields:
                field_id = field["name"]
                value = field["value_def"]
                field_code = field["field_code"]
                if value["data_type"] == "string":
                    f.write("    if (_%s != nil) {\n" % field_id)
                    f.write(
                        "        [coder setString:_%s forKey:%d];\n"
                        % (field_id, field_code)
                    )
                    f.write("    }\n")
                elif value["data_type"] == "enum":
                    f.write("    if (self.is_%s_set) {\n" % field_id)
                    f.write(
                        "        [coder setInteger:_%s_number.integerValue forKey:%d];\n"
                        % (field_id, field_code)
                    )
                    f.write("    }\n")
                else:
                    f.write("    if (!isnan(_%s)) {\n" % field_id)
                    f.write(
                        "        [coder setDouble:_%s forKey:%d];\n"
                        % (field_id, field_code)
                    )
                    f.write("    }\n")
            f.write("}\n")

        # generate event fields serializer
        if event_fields:
            f.write("- (void)serializeFields {\n")
            for field in event_fields:
                field_id = field["name"]
                value = field["value_def"]
                field_code = field["field_code"]

                if value["data_type"] == "string":
                    field_kind = "NSString"
                elif value["data_type"] == "enum":
                    field_kind = "NSNumber"
                    field_id += "_number"
                else:
                    field_kind = "numeric"
                f.write(
                    "    wam_maybe_serialize_%s_field(%d, _%s);\n"
                    % (field_kind, field_code, field_id)
                )
            f.write("}\n")

        # generate @synthesize statement for timer fields with milliseconds
        # units, and generate custom setters and getters for timer fields with
        # seconds units -- see why we need this in gen_objc_h() above
        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]

            if value["data_type"] == "enum":
                # implement custom checker, getter & setter backed up by NSNumber *
                objc_type, attr_kind = gen_objc_type(value)
                #  checker
                checker_method_name = "is_%s_set" % field_id
                f.write("- (BOOL)%s {\n" % checker_method_name)
                f.write("    return _%s_number != nil;\n" % field_id)
                f.write("}\n")
                #  getter
                f.write("- (%s)%s {\n" % (objc_type.strip(), field_id))
                f.write("    if ([self %s]) {\n" % checker_method_name)
                f.write("        return [_%s_number integerValue];\n" % field_id)
                f.write("    } else {\n")
                f.write("#if DEBUG\n")
                f.write("        NSAssert(NO, WAMEnumAccessViolationError);\n")
                f.write("#else\n")
                f.write(
                    "        [WAStackTrace uploadCriticalEventWithName:WAMEnumAccessViolationError];\n"
                )
                f.write("#endif\n")
                f.write("        return NSIntegerMin;\n")
                f.write("    }\n")
                f.write("}\n")
                #  setter
                f.write(
                    "- (void)set%s:(%s)newValue {\n"
                    % (field_id.capitalize(), objc_type.strip())
                )
                f.write("    _%s_number = @(newValue);\n" % field_id)
                f.write("}\n")
            elif value["type"] == "timer":
                f.write("@synthesize %s_milliseconds = _%s;\n" % (field_id, field_id))
                f.write("- (double)%s_seconds {\n" % field_id)
                # NOTE: we need this explicit wam_is_numeric_null() check here,
                # because dividing or multipying wam_numeric_null() (i.e.
                # 0xff..ff) results in a different floating-point NAN
                # representation, particularly when using compiler optimization
                # (i.e. compiling with -O<N>)
                f.write(
                    "    if (wam_is_numeric_null(_%s)) return wam_numeric_null();\n"
                    % field_id
                )
                f.write("    return _%s / 1000;\n" % field_id)
                f.write("}\n")
                f.write(
                    "- (void)set%s_seconds:(double)newValue {\n" % field_id.capitalize()
                )
                f.write("    if (!wam_is_numeric_null(newValue)) newValue *= 1000;\n")
                f.write("    _%s = newValue;\n" % field_id)
                f.write("}\n")

        # generate description for printing out the event on debug builds
        f.write("#if DEBUG\n")
        f.write("- (NSString *)description {\n")
        f.write(
            '    NSMutableString *description = [[NSMutableString alloc] initWithString:@"WamEvent%s["];\n'
            % event_id
        )
        for field in event_fields:
            field_id = field["name"]
            value = field["value_def"]
            if value["data_type"] == "bool":
                f.write("    if (!isnan(_%s)) {\n" % field_id)
                f.write(
                    '        [description appendString:[NSString stringWithFormat:@"%s=%%.0f| ", _%s]];\n'
                    % (field_id, field_id)
                )
                f.write("    }\n")
            elif value["data_type"] == "enum":
                f.write("    if (self.is_%s_set) {\n" % field_id)
                f.write(
                    '        [description appendString:[NSString stringWithFormat:@"%s=%%d| ", (int)_%s_number.integerValue]];\n'
                    % (field_id, field_id)
                )
                f.write("    }\n")
            elif value["data_type"] == "string":
                f.write("    if (_%s != nil) {\n" % field_id)
                f.write(
                    '        [description appendString:[NSString stringWithFormat:@"%s=%%@| ", _%s]];\n'
                    % (field_id, field_id)
                )
                f.write("    }\n")
            else:
                f.write("    if (!isnan(_%s)) {\n" % field_id)
                if value["data_type"] == "int":
                    f.write(
                        '        [description appendString:[NSString stringWithFormat:@"%s=%%.0f| ", _%s]];\n'
                        % (field_id, field_id)
                    )
                elif value["data_type"] == "float":
                    f.write(
                        '        [description appendString:[NSString stringWithFormat:@"%s=%%.3f| ", _%s]];\n'
                        % (field_id, field_id)
                    )
                f.write("    }\n")
        f.write('    [description appendString:@"]"];\n')
        f.write("    return description;\n")
        f.write("}\n")
        f.write("#endif\n")
        f.write("@end\n")


def gen_java_type(value, with_annotation=False, inside_wam=False):
    data_type = value["data_type"]
    type_name = value["type"]

    if data_type == "string":
        java_type = "String"
    elif data_type == "enum":
        if with_annotation:
            if inside_wam:
                java_type = "@Enums.%s.Constant Integer" % snake_to_upper_camelcase(
                    type_name
                )
            else:
                java_type = "@Wam.Enums.%s.Constant Integer" % snake_to_upper_camelcase(
                    type_name
                )
        else:
            java_type = "Integer"
    elif data_type == "bool":
        java_type = "Boolean"
    elif data_type == "int":
        java_type = "Long"
    elif data_type == "float":
        java_type = "Double"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False
    return java_type


def gen_android_serialize_method(f, schema, indent):
    f.write(
        indent
        + "// To reduce method count, we use this instead of a serialize method per subclass of Event\n"
    )

    f.write(
        indent + "public void serialize(@NonNull FieldSerializer fieldSerializer) {\n"
    )
    indent += " " * 4

    f.write(indent + "switch (this.code) {\n")
    indent += " " * 4

    for event in schema.events:
        if event.get("deprecated", False):
            continue  # Don't generate for deprecated events

        event_code = gen_event_code(event)
        event_class_name = "Wam" + snake_to_upper_camelcase(event["name"])

        f.write(
            indent
            + "case %d: // case of `serialize` for class: %s\n"
            % (event_code, event_class_name)
        )
        indent += " " * 4

        f.write(
            indent
            + "%s thisAs%s = (%s) this;\n"
            % (event_class_name, event_class_name, event_class_name)
        )

        for field in event.get("field", []):
            if field["value_def"].get("deprecated", False):
                continue  # Don't serialize deprecated fields

            field_code = field["field_code"]
            field_name = snake_to_camelcase(field["name"])
            # field_type = gen_java_type(field['value_def'])

            f.write(
                indent
                + "fieldSerializer.serialize(%d, thisAs%s.%s);\n"
                % (field_code, event_class_name, field_name)
            )

        f.write(indent + "break;\n")
        indent = indent[:-4]

    f.write(indent + "default:\n")
    f.write(indent + "    // Should never reach here\n")
    f.write(indent + '    Log.e("Event/ unexpected code");\n')

    indent = indent[:-4]
    f.write(indent + "}\n")

    indent = indent[:-4]
    f.write(indent + "}\n")
    return indent


def gen_android_to_string_method(f, schema, indent):
    f.write(
        indent
        + "// To reduce method count, we use this instead of a toString method per subclass of Event\n"
    )

    f.write(indent + "public String toString() {\n")
    indent += " " * 4

    f.write(indent + "StringBuilder sb = new StringBuilder(256);\n")

    f.write(indent + "switch (this.code) {\n")
    indent += " " * 4

    for event in schema.events:
        if event.get("deprecated", False):
            continue  # Don't generate for deprecated events

        event_code = gen_event_code(event)
        event_class_name = "Wam" + snake_to_upper_camelcase(event["name"])

        f.write(
            indent
            + "case %d: // case of `toString` for class: %s\n"
            % (event_code, event_class_name)
        )
        indent += " " * 4

        f.write(
            indent
            + "%s thisAs%s = (%s) this;\n"
            % (event_class_name, event_class_name, event_class_name)
        )
        f.write(indent + 'sb.append("%s {");\n' % event_class_name)

        for field in event.get("field", []):
            if field["value_def"].get("deprecated", False):
                continue  # Don't serialize deprecated fields

            field_code = field["field_code"]
            field_name = snake_to_camelcase(field["name"])
            # field_type = gen_java_type(field['value_def'])

            if field["value_def"]["data_type"] == "enum":
                field_type_name = snake_to_upper_camelcase(field["value_def"]["type"])
                field_value_arg = "Wam.Enums.%s.toLogString(thisAs%s.%s)" % (
                    field_type_name,
                    event_class_name,
                    field_name,
                )
            else:
                field_value_arg = "thisAs%s.%s" % (event_class_name, field_name)
            f.write(
                indent
                + 'Event.appendFieldToStringBuilder(sb, "%s", %s);\n'
                % (field_name, field_value_arg)
            )

        f.write(indent + "break;\n")
        indent = indent[:-4]

    f.write(indent + "default:\n")
    f.write(indent + "    // Should never reach here\n")
    f.write(indent + '    Log.e("Event/ unexpected code");\n')
    f.write(indent + '    return "";\n')

    indent = indent[:-4]
    f.write(indent + "}\n")

    f.write(indent + 'sb.append("}");\n')
    f.write(indent + "return sb.toString();\n")

    indent = indent[:-4]
    f.write(indent + "}\n")
    return indent


def gen_android_event_parent_class(f, schema):
    # Generate base sampling
    android_default_sampling = schema.schema_sampling.get("android")
    if android_default_sampling is None:
        print("No set-platform is defined for android", file=sys.stderr)
        sys.exit(1)

    f.write(
        """\
// GENERATED CODE - DO NOT EDIT
//
// This file was \x40generated by wamc - WhatsApp application metrics compiler

package com.whatsapp.fieldstats;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import com.whatsapp.fieldstats.events.*;
import com.whatsapp.fieldstats.FieldSerializer;
import com.whatsapp.perf.SamplingRate;
import com.whatsapp.util.Log;

public abstract class Event implements Cloneable {
    final int code;
    final SamplingRate samplingRate;
    public static final SamplingRate DEFAULT_SAMPLING_RATE = new SamplingRate(%d, %d, %d, false);
    @WamBuffer.BufferChannel final int channel;

    public Event(final int code) {
        this(code, DEFAULT_SAMPLING_RATE, WamBuffer.CHANNEL_REGULAR);
    }

    public Event(final int code, final SamplingRate samplingRate, @WamBuffer.BufferChannel final int channel) {
        this.code = code;
        this.samplingRate = samplingRate;
        this.channel = channel;
    }

    public SamplingRate getSamplingRate() {
        return samplingRate;
    }

    public Object clone() {
        try {
            return super.clone();
        }
        catch (CloneNotSupportedException e) {
            // This should never happen
            throw new InternalError(e.toString());
        }
    }

    public static void appendFieldToStringBuilder(@NonNull StringBuilder sb, @NonNull String fieldName, @Nullable Object fieldValue) {
        if (fieldValue != null) {
            sb.append(fieldName);
            sb.append("=");
            sb.append(fieldValue); // sb.append calls String.valueOf
            sb.append(", ");
        }
    }

"""
        % (
            android_default_sampling.get("debug_weight"),
            android_default_sampling.get("beta_weight"),
            android_default_sampling.get("release_weight"),
        )
    )

    indent = " " * 4
    indent = gen_android_serialize_method(f, schema, indent)
    _indent = gen_android_to_string_method(f, schema, indent)

    f.write("}\n")


def format_java_comment(x, indent=4, **kwargs):
    return format_c_comment(x, comment_open="/**", indent=indent, **kwargs)


def gen_android_attributes_and_enums(f, schema):
    file_header = """\
// GENERATED CODE - DO NOT EDIT
//
// This file was \x40generated by wamc - WhatsApp application metrics compiler

package com.whatsapp.fieldstats;

import androidx.annotation.IntDef;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.whatsapp.build.BuildInfo;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;


"""
    file_footer = "\n"

    f.write(file_header)

    # Wam class
    f.write("public final class Wam {\n")

    # generate enum definitions
    indent = " " * 4
    f.write("\n")
    f.write(indent + "public static final class Enums {\n")

    indent = " " * 8

    def format_intdef_classheader(enum_id):
        return indent + "public static class %(enum_id)s {\n" % {"enum_id": enum_id}

    def format_intdef_const(enum_id, name, code, doc, deprecated=False):
        my_indent = indent + " " * 4
        builder = format_java_comment(doc, indent=my_indent)
        builder += (
            my_indent
            + "public static final %(deprecated)sint %(name)s = %(code)d;\n"
            % {
                "name": name,
                "code": code,
                "deprecated": "@Deprecated " if deprecated else "",
            }
        )
        return builder

    def format_intdef_interface(constant_names):
        my_indent = indent + " " * 4
        builder = my_indent + "@IntDef({"
        for i, name in enumerate(constant_names):
            if i != 0:
                builder += ", "
            builder += name
        builder += "})\n"
        builder += my_indent + "@Retention(RetentionPolicy.SOURCE)\n"
        builder += my_indent + "public @interface Constant {}\n"

        return builder

    def format_intdef_tostring(constant_names):
        my_indent = indent + " " * 4
        builder = (
            my_indent
            + "public static @Nullable String toLogString(@Nullable final @Constant Integer value) {\n"
        )
        my_indent = indent + " " * 8
        builder += my_indent + "if (value == null) {\n"
        builder += my_indent + "    return null;\n"
        builder += my_indent + "}\n"
        builder += my_indent + "if (!BuildInfo.isDebugBuild()) {\n"
        builder += my_indent + "    return value.toString();\n"
        builder += my_indent + "}\n"

        builder += my_indent + "switch (value) {\n"
        my_indent = indent + " " * 12
        for name in constant_names:
            builder += my_indent + "case %(name)s:\n" % {"name": name}
            builder += my_indent + """    return "%(lowercase_name)s";\n""" % {
                "lowercase_name": name.lower()
            }
        builder += my_indent + "default:\n"
        builder += (
            my_indent
            + """    throw new IllegalArgumentException("Unknown enum value: " + value);\n"""
        )
        my_indent = indent + " " * 8
        builder += my_indent + "}\n"
        my_indent = indent + " " * 4
        builder += my_indent + "}\n"

        return builder

    for enum in schema.enums:
        enum_id = snake_to_upper_camelcase(enum["name"])

        f.write("\n")
        f.write(format_java_comment(get_doc(enum), indent=indent))

        if enum.get("deprecated", False):
            f.write(indent + "@Deprecated\n")

        f.write(format_intdef_classheader(enum_id))

        constant_names = []
        for constant in enum["constant"]:
            name = constant["name"].upper()
            constant_names.append(name)
            f.write(
                format_intdef_const(
                    enum_id,
                    name,
                    constant["code"],
                    get_doc(constant),
                    deprecated=constant.get("deprecated", False),
                )
            )

        f.write("\n")
        f.write(format_intdef_tostring(constant_names))
        f.write("\n")
        f.write(format_intdef_interface(constant_names))
        f.write(indent + "}\n")

    indent = " " * 4
    f.write(indent + "}\n")  # Enums

    # generate attributes
    attributes = [x["value_def"] for x in schema.common_attributes]

    indent = " " * 4
    for value in attributes:
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime

        name = value["name"]
        code = gen_value_code(value)
        java_type = gen_java_type(value, with_annotation=True, inside_wam=True)

        f.write("\n")
        f.write(format_java_comment(get_doc(value)))
        if value.get("deprecated", False):
            f.write(indent + "@Deprecated\n")

        f.write(
            f"{indent}public static void set{snake_to_upper_camelcase(name)}(@NonNull WamCommonAttributes wamCommonAttributes, {java_type} value) {{\n"
        )
        indent += " " * 4
        if not value.get("deprecated", False):
            # Write in regular channel
            f.write(
                f"{indent}wamCommonAttributes.setAttribute({code}, value, WamBuffer.CHANNEL_REGULAR);\n"
            )
            # Write in realtime channel
            f.write(
                f"{indent}wamCommonAttributes.setAttribute({code}, value, WamBuffer.CHANNEL_REAL_TIME);\n"
            )
            if value["enabled_for_anonymous"]:
                # Whether to also write in anonymous channel
                f.write(
                    f"{indent}wamCommonAttributes.setAttribute({code}, value, WamBuffer.CHANNEL_PRIVATE_STATS);\n"
                )
        indent = indent[:-4]
        f.write(f"{indent}}}\n")

    f.write("\n")

    indent = " " * 4

    # generate codes for special attributes for wam runtime
    wam_client_attributes = [x for x in attributes if is_wam_client_attribute(x)]
    f.write("\n")
    for value in wam_client_attributes:
        f.write(
            indent
            + "static final int ATTRIBUTE_%s = %d;\n"
            % (value["name"].upper(), gen_value_code(value))
        )

    f.write("}\n")  # Wam
    f.write(file_footer)


def have_fields_with_wam_class(fields):
    for field in fields:
        java_type = gen_java_type(field["value_def"], with_annotation=True)
        if java_type.startswith("@Wam."):
            return True
    return False


def gen_android_import_str(contains_fields, need_to_import_wam_class):
    import_str = "import androidx.annotation.NonNull;\n"

    if contains_fields:
        import_str += "import androidx.annotation.Nullable;\n"

    import_str += "\n"
    import_str += "import com.whatsapp.fieldstats.Event;\n"
    import_str += "import com.whatsapp.fieldstats.FieldSerializer;\n"
    import_str += "import com.whatsapp.fieldstats.WamBuffer;\n"
    import_str += "import com.whatsapp.perf.SamplingRate;\n"
    if need_to_import_wam_class:
        import_str += "import com.whatsapp.fieldstats.Wam;\n"
    return import_str


def gen_android_event(f, event):
    fields = event.get("field", [])

    file_header = """\
// GENERATED CODE - DO NOT EDIT
//
// This file was \x40generated by wamc - WhatsApp application metrics compiler

package com.whatsapp.fieldstats.events;

"""
    need_to_import_wam_class = have_fields_with_wam_class(fields)
    file_header += (
        gen_android_import_str(len(fields) > 0, need_to_import_wam_class) + "\n"
    )

    file_footer = "\n"

    f.write(file_header)

    indent = ""

    event_code = gen_event_code(event)
    name = event["name"]
    java_name = "Wam" + snake_to_upper_camelcase(name)

    f.write("\n")
    f.write(format_java_comment(get_doc(event), indent=indent))
    if event.get("deprecated", False):
        f.write(indent + "@Deprecated\n")

    # We want wam_client_errors and the daily event to be extensible
    if event["name"] == "wam_client_errors" or event["name"] == "daily":
        f.write(indent + "public class %s extends Event {\n" % java_name)
    else:
        f.write(indent + "public final class %s extends Event {\n" % java_name)

    indent = " " * 4

    # Generate event fields
    for field in fields:
        name = field["name"]
        value = field["value_def"]
        java_type = gen_java_type(value, with_annotation=True)

        f.write(format_java_comment(get_doc(value), indent=indent))
        if value.get("deprecated", False):
            f.write(indent + "@Deprecated\n")

        f.write(
            indent + "@Nullable public %s %s;\n" % (java_type, snake_to_camelcase(name))
        )

    f.write("\n")
    f.write(indent + "public %s() {\n" % java_name)
    indent += " " * 4

    f.write(indent + "super(%d,\n" % event_code)
    indent += " " * 4

    # generate sampling rate static final field and constructor
    if "set_platform" in event and "android" in event["set_platform"]:
        sampling_spec_dict = event["set_platform"]["android"]
        if "event" in sampling_spec_dict:
            event_sampling_spec = sampling_spec_dict["event"]
            debug = event_sampling_spec["debug_weight"]
            beta = event_sampling_spec["beta_weight"]
            release = event_sampling_spec["release_weight"]
            f.write(
                indent + "new SamplingRate(%d, %d, %d, false)" % (debug, beta, release)
            )
        elif "schema" in sampling_spec_dict:
            f.write(indent + "Event.DEFAULT_SAMPLING_RATE")
        else:
            print(
                "error: all android event needs a sampling spec defined, either at schema level or event level",
                file=sys.stderr,
            )
    else:
        print(
            "error: all android event needs a sampling spec defined, either at schema level or event level",
            file=sys.stderr,
        )
    f.write(",\n")

    if event["realtime"]:
        channel_arg = "WamBuffer.CHANNEL_REAL_TIME"
    elif event["anonymous"]:
        channel_arg = "WamBuffer.CHANNEL_PRIVATE_STATS"
    else:
        channel_arg = "WamBuffer.CHANNEL_REGULAR"
    f.write(f"{indent}{channel_arg}\n")

    indent = indent[:-4]
    f.write(indent + ");\n")

    indent = indent[:-4]
    f.write(indent + "}\n")

    # (for wam_client_errors only) generate isEmpty
    if event["name"] == "wam_client_errors":
        f.write("\n")
        indent = " " * 4
        f.write(indent + "public final boolean isEmpty() {\n")

        indent += " " * 4
        f.write(indent + "boolean result = true;\n")
        for field in fields:
            name = field["name"]
            f.write(
                indent + "result &= this.%s == null;\n" % (snake_to_camelcase(name))
            )
        f.write(indent + "return result;\n")

        indent = " " * 4
        f.write(indent + "}\n")  # isEmpty

    # (for wam_client_errors only) generate clear
    if event["name"] == "wam_client_errors":
        f.write("\n")
        indent = " " * 4
        f.write(indent + "public final void clear() {\n")

        indent += " " * 4
        for field in fields:
            name = field["name"]
            f.write(indent + "this.%s = null;\n" % (snake_to_camelcase(name)))

        indent = " " * 4
        f.write(indent + "}\n")  # clear

    # (for wam_client_errors only) generate setters
    if event["name"] == "wam_client_errors":
        for field in fields:
            name = field["name"]
            value = field["value_def"]
            java_type = gen_java_type(value, with_annotation=True)

            if java_type != "Boolean":
                continue

            f.write("\n")
            indent = " " * 4

            if value.get("deprecated", False):
                f.write(indent + "@Deprecated\n")
            f.write(
                indent
                + "public final void set%s() {\n"
                % (snake_to_camelcase(name, capitalize_first=True))
            )

            indent += " " * 4
            f.write(indent + "this.%s = true;\n" % (snake_to_camelcase(name)))
            indent = " " * 4
            f.write(indent + "}\n")  # setXXX

    # end of event
    f.write("}\n")  # event

    f.write(file_footer)


def gen_android_stubs(androidFolder, schema):
    # Generate Attributes and Enums
    with_open_file(
        os.path.join(androidFolder, "Wam.java"),
        lambda f: gen_android_attributes_and_enums(f, schema),
    )

    # Remove old event classes
    eventsFolder = ensure_dir(androidFolder, "events")
    oldClasses = [
        os.path.join(eventsFolder, f)
        for f in os.listdir(eventsFolder)
        if f.endswith(".java")
    ]
    for f in oldClasses:
        os.remove(f)

    with_open_file(
        os.path.join(androidFolder, "Event.java"),
        lambda f: gen_android_event_parent_class(f, schema),
    )

    # Generate Events
    for event in schema.events:
        with_open_file(
            os.path.join(
                eventsFolder, "Wam" + snake_to_upper_camelcase(event["name"]) + ".java"
            ),
            lambda f: gen_android_event(f, event),
        )


def format_python_comment(s, indent="", is_multiline=False):
    if s == "":
        return ""
    if isinstance(indent, int):
        indent = " " * indent

    initial_indent = indent + '"""\n' + indent if is_multiline else indent + "# "
    subsequent_indent = indent if is_multiline else indent + "# "
    close_indent = "\n" + indent + '"""' if is_multiline else ""

    wrapper = textwrap.TextWrapper(
        initial_indent=initial_indent, subsequent_indent=subsequent_indent, width=80
    )
    return wrapper.fill(s) + close_indent + "\n"


def gen_bloks_attributes_and_enums(f, schema):
    file_header = """\
# \x40oncall whatsapp_android_payments
#
# GENERATED CODE - DO NOT EDIT
#
# This file was \x40generated by wamc - WhatsApp application metrics compiler
from util.enum import Enum


"""
    file_footer = "\n"

    f.write(file_header)
    f.write("class Wam:\n")
    indent = " " * 4
    f.write(indent + "class Enums:")

    enum_indent = " " * 8
    enum_content_indent = " " * 12
    for enum in schema.enums:
        f.write("\n")
        enum_id = enum["name"]
        f.write(enum_indent + "class %s(Enum):\n" % snake_to_upper_camelcase(enum_id))
        enum_doc = get_doc(enum)
        f.write(
            format_python_comment(
                enum_doc, indent=enum_content_indent, is_multiline=True
            )
        )
        if enum_doc != "":
            f.write("\n")

        for constant in enum["constant"]:
            name = constant["name"]
            f.write(
                format_python_comment(get_doc(constant), indent=enum_content_indent)
            )
            f.write(
                enum_content_indent
                + '%s%s = "%d|%s"\n'
                % (
                    name.upper(),
                    "_DEPRECATED" if constant.get("deprecated", False) else "",
                    constant["code"],
                    name.lower(),
                )
            )


def gen_bloks_event_parent_class(f, schema):
    # Generate base sampling
    android_default_sampling = schema.schema_sampling.get("android")
    if android_default_sampling is None:
        print("No set-platform is defined for android", file=sys.stderr)
        sys.exit(1)

    f.write(
        """\
# \x40oncall whatsapp_android_payments
#
# GENERATED CODE - DO NOT EDIT
#
# This file was \x40generated by wamc - WhatsApp application metrics compiler
from typing import Dict, Optional, Union

from bloks.lispy.bindings import WhatsAppBindings
from bloks.lispy.lang import LiteralTypes, ValueReference
from bloks.lispy.lib import types
from util.enum import Enum


ValueType = Union[types.String, types.Number, ValueReference, LiteralTypes]


class SamplingRate:
    def __init__(
        self,
        sample_rate_debug: int = %d,
        sample_rate_beta: int = %d,
        sample_rate_release: int = %d,
        log_all_for_debug: bool = False,
    ) -> None:
        self.sample_rate_debug = sample_rate_debug
        self.sample_rate_beta = sample_rate_beta
        self.sample_rate_release = sample_rate_release
        self.log_all_for_debug = log_all_for_debug

    def build(self) -> types.Map:
        return types.Map.of(
            # pyre-ignore[6]: Expected `typing.Mapping[Union[str, types.String],
            # Union[ValueReference, bool, float, int, str, types.Number,
            # types.String]]` for 1st anonymous parameter to call `types.Map.of`
            # but got `Dict[str, int]`.
            {
                "sample_rate_debug": self.sample_rate_debug,
                "sample_rate_beta": self.sample_rate_beta,
                "sample_rate_release": self.sample_rate_release,
                "log_all_for_debug": self.log_all_for_debug,
            }
        )


class Event:
    class SerializeType(Enum):
        BOOL = 1
        LONG = 2
        FLOAT = 3
        STRING = 4
        ENUM = 5

    @staticmethod
    def initial_state() -> Dict[str, str]:
        return {}

    @staticmethod
    def new_state() -> types.Map:
        return types.Map.of({})

    @staticmethod
    def to_float(value: Union[float, types.Float]) -> types.Long:
        # intentionally done to preserve precision points
        # pyre-ignore[6]: Expected `Union[int, types.Long]` for 1st anonymous
        # parameter to call `types.Long.of` but got `Union[float, types.Float]`.
        return types.Long.of(value)

    def __init__(
        self,
        name: str,
        code: int,
        is_realtime: bool,
        sample_rate: SamplingRate,
        event_state: Optional[types.Map] = None,
    ) -> None:
        self.name = name
        self.code = code
        self.is_realtime = is_realtime
        self.sample_rate = sample_rate
        if event_state is None:
            event_state = Event.new_state()
        self.event_state: types.Map = event_state

    def update(self, key: str, value: ValueType) -> types.Void:
        update: Dict[Union[str, types.String], ValueType] = {key: value}
        return self.event_state.update(update)

    def build_fields(self) -> types.Array:
        pass

    def send(self) -> types.Void:
        return WhatsAppBindings.send_fieldstat(
            types.String.of(self.name),
            types.Integer.of(self.code),
            types.Bool.of(self.is_realtime),
            self.sample_rate.build(),
            self.build_fields(),
        )
"""
        % (
            android_default_sampling.get("debug_weight"),
            android_default_sampling.get("beta_weight"),
            android_default_sampling.get("release_weight"),
        )
    )


def has_non_enum_field(fields):
    for field in fields:
        value = field["value_def"]
        deprecated = value.get("deprecated", False)
        is_enum = value["data_type"] == "enum"
        if not deprecated and not is_enum:
            return True
    return False


def get_bloks_type(value):
    data_type = value["data_type"]
    if data_type == "string":
        return "Union[str, types.String]"
    elif data_type == "enum":
        return "Wam.Enums.%s" % snake_to_upper_camelcase(value["type"])
    elif data_type == "bool":
        return "Union[bool, types.Bool]"
    elif data_type == "int":
        return "Union[int, types.Long]"
    elif data_type == "float":
        return "Union[float, types.Float]"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False


def get_bloks_type_to_str(field):
    name = field["name"]
    data_type = field["value_def"]["data_type"]
    if data_type == "string":
        return name.lower()
    elif data_type == "enum":
        return name.lower() + ".value"
    elif data_type == "bool":
        return "types.Bool.of(%s)" % name.lower()
    elif data_type == "int":
        return "types.Long.of(%s)" % name.lower()
    elif data_type == "float":
        # TODO(frederil): use long due to precision points
        return "Event.to_float(%s)" % name.lower()
    else:
        print(("unrecognized type " + str(data_type)))
        assert False


def get_bloks_type_serialized(data_type):
    form = "Event.SerializeType.%s"
    if data_type == "string":
        return form % "STRING"
    elif data_type == "enum":
        return form % "ENUM"
    elif data_type == "bool":
        return form % "BOOL"
    elif data_type == "int":
        return form % "LONG"
    elif data_type == "float":
        return form % "FLOAT"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False


def gen_bloks_event(f, event):
    fields = event.get("field", [])
    need_to_import_wam_class = have_fields_with_wam_class(fields)

    file_header = """\
# \x40oncall whatsapp_android_payments
#
# GENERATED CODE - DO NOT EDIT
#
# This file was \x40generated by wamc - WhatsApp application metrics compiler
"""
    f.write(file_header)

    if has_non_enum_field(fields):
        f.write("from typing import Optional, Union\n\n")
    else:
        f.write("from typing import Optional\n\n")

    f.write(
        "from bloks.apps.whatsapp.payment.common.fieldstats.fieldstats import Event, SamplingRate\n"
    )

    if need_to_import_wam_class:
        f.write("from bloks.apps.whatsapp.payment.common.fieldstats.wam import Wam\n")
    f.write("from bloks.lispy.lib import types\n\n\n")

    event_code = gen_event_code(event)
    event_class_name = "Wam" + snake_to_upper_camelcase(event["name"])

    f.write("class %s(Event):\n" % event_class_name)

    indent = " " * 4
    event_doc = get_doc(event)
    f.write(format_python_comment(event_doc, indent=indent, is_multiline=True))
    if event_doc != "":
        f.write("\n")

    method_indent = " " * 8

    # sample rate
    sample_rate = "SamplingRate()"
    if "set_platform" in event and "android" in event["set_platform"]:
        sampling_spec_dict = event["set_platform"]["android"]
        if "event" in sampling_spec_dict:
            event_sampling_spec = sampling_spec_dict["event"]
            debug = event_sampling_spec["debug_weight"]
            beta = event_sampling_spec["beta_weight"]
            release = event_sampling_spec["release_weight"]
            sample_rate = "SamplingRate(%d, %d, %d, False)" % (debug, beta, release)
        elif "schema" in sampling_spec_dict:
            sample_rate = "SamplingRate()"
        else:
            print(
                "error: all bloks events need a sampling spec defined, either at schema level or event level",
                file=sys.stderr,
            )
    else:
        print(
            "error: all bloks events needs a sampling spec defined, either at schema level or event level",
            file=sys.stderr,
        )

    # constructor
    f.write(
        indent
        + "def __init__(self, event_state: Optional[types.Map] = None) -> None:\n"
    )
    f.write(
        method_indent
        + 'super().__init__("%s", %d, %s, %s, event_state=event_state)\n'
        % (event_class_name, event_code, event["realtime"], sample_rate)
    )

    # field setters
    for field in fields:
        deprecated = field["value_def"].get("deprecated", False)
        if deprecated:
            continue

        field_code = field["field_code"]
        field_name = field["name"]
        field_type = field["value_def"]["data_type"]
        f.write("\n")
        f.write(
            indent
            + "def set_%s(self, %s: %s) -> types.Void:\n"
            % (
                field_name.lower(),
                field_name.lower(),
                get_bloks_type(field["value_def"]),
            )
        )
        f.write(
            format_python_comment(
                get_doc(field["value_def"]), indent=method_indent, is_multiline=True
            )
        )
        f.write(
            method_indent
            + 'return super().update("%d", %s)\n\n'
            % (field_code, get_bloks_type_to_str(field))
        )

    f.write("\n")
    f.write(indent + "def build_fields(self) -> types.Array:\n")
    f.write(method_indent + "return types.Array.of(\n")
    f.write(method_indent + indent + "[\n")
    for field in fields:
        deprecated = field["value_def"].get("deprecated", False)
        if deprecated:
            continue

        field_code = field["field_code"]
        field_name = field["name"]
        field_type = field["value_def"]["data_type"]
        field_indent = " " * 16

        f.write(field_indent + "%d,\n" % field_code)
        f.write(field_indent + '"%s",\n' % field_name)
        f.write(field_indent + "%s.value,\n" % get_bloks_type_serialized(field_type))
        f.write(field_indent + 'self.event_state.get("%d"),\n' % field_code)

    f.write(method_indent + indent + "]\n")
    f.write(method_indent + ")\n")


# ==== BEGIN BLOKS INSTAGRAM GEN LOGIC ====
def gen_bloks_stubs(bloksFolder, schema):
    # Remove old event classes
    eventsFolder = ensure_dir(bloksFolder, "events")
    oldClasses = [
        os.path.join(eventsFolder, f)
        for f in os.listdir(eventsFolder)
        if f.endswith(".py")
    ]
    oldClasses += [
        os.path.join(bloksFolder, f)
        for f in os.listdir(bloksFolder)
        if f.endswith(".py")
    ]
    for f in oldClasses:
        os.remove(f)

    # Generate Attributes and Enums
    with_open_file(
        os.path.join(bloksFolder, "wam.py"),
        lambda f: gen_bloks_attributes_and_enums(f, schema),
    )

    # generate base event and sampling rate class
    with_open_file(
        os.path.join(bloksFolder, "fieldstats.py"),
        lambda f: gen_bloks_event_parent_class(f, schema),
    )

    # Generate Events
    for event in schema.events:
        with_open_file(
            os.path.join(eventsFolder, "wam_" + event["name"].lower() + ".py"),
            lambda f: gen_bloks_event(f, event),
        )


# ==== END BLOKS INSTAGRAM GEN LOGIC ====

# ==== BEGIN BLOKS WWW GEN LOGIC ====
def format_php_comment(x, indent=2, **kwargs):
    return format_c_comment(x, comment_open="/**", indent=indent, **kwargs)


def gen_bloks_www_attributes_and_enums(f, schema):
    file_header = """\
<?hh
// (c) Facebook, Inc. and its affiliates. Confidential and proprietary.
/**
 * This file is generated. Do not modify it manually!
 *
 * This file was \x40generated by wamc - WhatsApp application metrics compiler
 */

namespace BKS\\WA\\Fieldstats\\Enums;

<<\\Oncalls('whatsapp_android_payments')>>
"""

    f.write(file_header)

    for enum in schema.enums:
        f.write("\n")
        enum_doc = get_doc(enum)
        f.write(format_php_comment(enum_doc, indent=0))
        enum_id = enum["name"]
        f.write("enum %s: string as string {\n" % snake_to_upper_camelcase(enum_id))

        for constant in enum["constant"]:
            name = constant["name"]
            f.write(format_php_comment(get_doc(constant), indent=2))
            f.write(
                '  %s%s = "%d|%s";\n'
                % (
                    name.upper(),
                    "_DEPRECATED" if constant.get("deprecated", False) else "",
                    constant["code"],
                    name.lower(),
                )
            )
        f.write("}\n")


def gen_bloks_www_sampling_rate_class(f, schema):
    # Generate base sampling
    android_default_sampling = schema.schema_sampling.get("android")
    if android_default_sampling is None:
        print("No set-platform is defined for android", file=sys.stderr)
        sys.exit(1)

    f.write(
        """\
<?hh
// (c) Facebook, Inc. and its affiliates. Confidential and proprietary.
/**
 * This file is generated. Do not modify it manually!
 *
 * This file was \x40generated by wamc - WhatsApp application metrics compiler
 */

namespace BKS\\WA\\Fieldstats;

<<\\Oncalls('whatsapp_android_payments')>>
final class SamplingRate {

  public function __construct(
    private int $sampleRateDebug = %d,
    private int $sampleRateBeta = %d,
    private int $sampleRateRelease = %d,
    private bool $logAllForDebug = false,
  ) {}

  public function build(): \\BKSExpression<\\BKSClientMap<\\BKSClientValue, \\BKSClientValue>> {
    return \\BKS\\Bk\\Map\\Make(
      \\BKSArray::const(
        \\BKSString::const('sample_rate_debug'),
        \\BKSString::const('sample_rate_beta'),
        \\BKSString::const('sample_rate_release'),
        \\BKSString::const('log_all_for_debug'),
      ),
      \\BKSArray::const(
        \\BKSInt::const($this->sampleRateDebug),
        \\BKSInt::const($this->sampleRateBeta),
        \\BKSInt::const($this->sampleRateRelease),
        \\BKSBool::const($this->logAllForDebug),
      ),
    );
  }
}
"""
        % (
            android_default_sampling.get("debug_weight"),
            android_default_sampling.get("beta_weight"),
            android_default_sampling.get("release_weight"),
        )
    )


def gen_bloks_www_event_parent_class(f):
    f.write(
        """\
<?hh
// (c) Facebook, Inc. and its affiliates. Confidential and proprietary.
/**
 * This file is generated. Do not modify it manually!
 *
 * This file was \x40generated by wamc - WhatsApp application metrics compiler
 */

namespace BKS\\WA\\Fieldstats;

<<\\Oncalls('whatsapp_android_payments')>>

enum SerializeType: int as int {
  BOOL = 1;
  LONG = 2;
  FLOAT = 3;
  STRING = 4;
  ENUM = 5;
}

abstract class Event {

  public function __construct(
    private string $name,
    private int $code,
    private bool $isRealtime,
    private SamplingRate $sampleRate,
  ) {}

  abstract protected function buildFields(): \\BKSArray<\\BKSClientValue>;

  public function send(): \\BKSExpression<\\BKSClientVoid> {
    return \\BKS\\Wa\\SendFieldStat(
      \\BKSString::const($this->name),
      \\BKSInt::const($this->code),
      \\BKSBool::const($this->isRealtime),
      $this->sampleRate->build(),
      $this->buildFields(),
    );
  }
}
"""
    )


def get_bloks_www_member_type(value):
    data_type = value["data_type"]
    if data_type == "string" or data_type == "enum":
        return "\\BKSExpression<\\BKSClientString>"
    elif data_type == "bool":
        return "\\BKSExpression<\\BKSClientBool>"
    elif data_type == "int":
        return "\\BKSExpression<\\BKSClientLong>"
    elif data_type == "float":
        return "\\BKSExpression<\\BKSClientFloat>"
    else:
        print("unrecognized type " + str(data_type))
        assert False


def get_bloks_www_type(value):
    data_type = value["data_type"]
    if data_type == "string":
        return "\\BKSExpression<\\BKSClientString>"
    elif data_type == "enum":
        return "Enums\\%s" % snake_to_upper_camelcase(value["type"])
    elif data_type == "bool":
        return "\\BKSExpression<\\BKSClientBool>"
    elif data_type == "int":
        return "\\BKSExpression<\\BKSClientLong>"
    elif data_type == "float":
        return "\\BKSExpression<\\BKSClientFloat>"
    else:
        print("unrecognized type " + str(data_type))
        assert False


def get_bloks_www_type_serialized(data_type):
    form = "SerializeType::%s"
    if data_type == "string":
        return form % "STRING"
    elif data_type == "enum":
        return form % "ENUM"
    elif data_type == "bool":
        return form % "BOOL"
    elif data_type == "int":
        return form % "LONG"
    elif data_type == "float":
        return form % "FLOAT"
    else:
        print("unrecognized type " + str(data_type))
        assert False


def get_bloks_www_type_set(data_type):
    if data_type == "enum":
        return "\\BKSString::const($%s)"
    return "$%s"


def gen_bloks_www_event(f, event):
    fields = event.get("field", [])
    fields_non_deprecated = [
        field for field in fields if not field["value_def"].get("deprecated", False)
    ]
    need_to_import_wam_class = have_fields_with_wam_class(fields)

    file_header = """\
<?hh
// (c) Facebook, Inc. and its affiliates. Confidential and proprietary.
/**
 * This file is generated. Do not modify it manually!
 *
 * This file was \x40generated by wamc - WhatsApp application metrics compiler
 */

namespace BKS\\WA\\Fieldstats;

<<\\Oncalls('whatsapp_android_payments')>>
"""
    f.write(file_header)

    event_code = gen_event_code(event)
    event_class_name = "Wam" + snake_to_upper_camelcase(event["name"])

    event_doc = get_doc(event)
    f.write(format_php_comment(event_doc, indent=0))
    if event_doc != "":
        f.write("\n")

    f.write("final class %s extends Event {\n\n" % event_class_name)

    indent = " " * 2
    for field in fields_non_deprecated:
        f.write(
            indent
            + "private ?%s $%s;\n"
            % (
                get_bloks_www_member_type(field["value_def"]),
                snake_to_camelcase(field["name"]),
            )
        )
    if len(fields_non_deprecated) > 0:
        f.write("\n")

    # sample rate
    sample_rate = "new SamplingRate()"
    if "set_platform" in event and "android" in event["set_platform"]:
        sampling_spec_dict = event["set_platform"]["android"]
        if "event" in sampling_spec_dict:
            event_sampling_spec = sampling_spec_dict["event"]
            debug = event_sampling_spec["debug_weight"]
            beta = event_sampling_spec["beta_weight"]
            release = event_sampling_spec["release_weight"]
            sample_rate = "new SamplingRate(%d, %d, %d, false)" % (debug, beta, release)
        elif "schema" in sampling_spec_dict:
            sample_rate = "new SamplingRate()"
        else:
            print(
                "error: all bloks events need a sampling spec defined, either at schema level or event level",
                file=sys.stderr,
            )
    else:
        print(
            "error: all bloks events needs a sampling spec defined, either at schema level or event level",
            file=sys.stderr,
        )

    # constructor
    f.write(indent + "public function __construct() {\n")
    indent = " " * 4
    f.write(indent + "parent::__construct(\n")
    indent = " " * 6
    f.write(indent + '"%s",\n' % event_class_name)
    f.write(indent + "%d,\n" % event_code)
    f.write(indent + "%s,\n" % ("true" if event["realtime"] else "false"))
    f.write(indent + "%s\n" % sample_rate)
    indent = " " * 4
    f.write(indent + ");\n")
    indent = " " * 2
    f.write(indent + "}\n")

    # field setters
    for field in fields_non_deprecated:
        field_code = field["field_code"]
        field_name = field["name"]
        field_type = field["value_def"]["data_type"]
        f.write("\n")
        f.write(format_php_comment(get_doc(field["value_def"]), indent=indent))
        f.write(
            indent
            + "public function set%s(%s $%s): %s {\n"
            % (
                snake_to_upper_camelcase(field_name),
                get_bloks_www_type(field["value_def"]),
                field_name,
                event_class_name,
            )
        )
        indent = " " * 4
        f.write(
            indent
            + "$this->%s = %s;\n"
            % (
                snake_to_camelcase(field_name),
                get_bloks_www_type_set(field_type) % field_name,
            )
        )
        f.write(indent + "return $this;\n")
        indent = " " * 2
        f.write(indent + "}\n")

    f.write("\n")
    indent = " " * 2
    f.write(indent + "<<__Override>>")
    f.write(
        indent + "protected function buildFields(): \\BKSArray<\\BKSClientValue> {\n"
    )
    indent = " " * 4
    f.write(indent + "return \\BKSArray::const(\n")
    for field in fields_non_deprecated:

        field_code = field["field_code"]
        field_name = field["name"]
        field_type = field["value_def"]["data_type"]
        indent = " " * 6

        f.write(indent + "\\BKSInt::const(%d),\n" % field_code)
        f.write(indent + "\\BKSString::const('%s'),\n" % field_name)
        f.write(
            indent
            + "\\BKSInt::const(%s),\n" % get_bloks_www_type_serialized(field_type)
        )
        f.write(
            indent
            + "$this->%s !== null ? $this->%s : new \\BKSNull(),\n"
            % (snake_to_camelcase(field_name), snake_to_camelcase(field_name))
        )

    indent = " " * 4
    f.write(indent + ");\n")
    indent = " " * 2
    f.write(indent + "}\n")
    f.write("}\n")


def gen_bloks_www_stubs(bloksFolder, schema):
    # Remove old event classes
    eventsFolder = os.path.join(bloksFolder, "events")
    ensure_dir(eventsFolder)
    oldClasses = [
        os.path.join(eventsFolder, f)
        for f in os.listdir(eventsFolder)
        if f.endswith(".php")
    ]
    oldClasses += [
        os.path.join(bloksFolder, f)
        for f in os.listdir(bloksFolder)
        if f.endswith(".php")
    ]
    for f in oldClasses:
        os.remove(f)

    # Generate Attributes and Enums
    with_open_file(
        os.path.join(bloksFolder, "Enums.php"),
        lambda f: gen_bloks_www_attributes_and_enums(f, schema),
    )

    # generate base event and sampling rate class
    with_open_file(
        os.path.join(bloksFolder, "Event.php"),
        lambda f: gen_bloks_www_event_parent_class(f),
    )

    # generate base event and sampling rate class
    with_open_file(
        os.path.join(bloksFolder, "SamplingRate.php"),
        lambda f: gen_bloks_www_sampling_rate_class(f, schema),
    )

    # Generate Events
    for event in schema.events:
        with_open_file(
            os.path.join(
                eventsFolder, "Wam" + snake_to_upper_camelcase(event["name"]) + ".php"
            ),
            lambda f: gen_bloks_www_event(f, event),
        )


# ==== END BLOKS WWW GEN LOGIC ====


def gen_charp_enums(f, schema):
    # format enum constant definition
    def format_enum_const(id, code):
        return id.upper() + " = " + str(code) + ",\n"

    # generate enum definitions
    for enum in schema.enums:
        f.write(format_c_comment(get_doc(enum), indent=4))

        enum_id = "wam_enum_" + enum["name"]
        f.write("    public enum " + enum_id + " {\n")

        for c in enum["constant"]:
            f.write(format_c_comment(get_doc(c), indent=8))

            elem = format_enum_const(c["name"], c["code"])
            f.write("        " + elem)
        f.write("    };\n\n")


def gen_csharp_type(value):
    data_type = value["data_type"]
    type_name = value["type"]

    if data_type == "string":
        csharp_type = "string"
    elif data_type == "enum":
        csharp_type = "wam_enum_" + type_name + "?"
    elif data_type == "bool":
        csharp_type = "bool?"
    elif data_type == "int":
        csharp_type = "long?"
    elif data_type == "float":
        csharp_type = "double?"
    else:
        print(("unrecognized type " + str(data_type)))
        assert False
    return csharp_type


def gen_csharp(f, schema):
    file_header = """\
/* GENERATED CODE - DO NOT EDIT
/*
/* this file was \x40generated by wamc - WhatsApp field metrics compiler */\n
using System;
using WhatsAppNative;

namespace WhatsApp
{
"""
    f.write(file_header)

    gen_charp_enums(f, schema)

    # generate attributes
    attributes = [x["value_def"] for x in schema.common_attributes]
    assign_attribute_offsets(attributes)

    f.write("    public static partial class Wam\n")
    f.write("    {\n")

    for value in attributes:
        if is_wam_client_attribute(value):
            continue  # skip special attributes used by wam client runtime

        f.write(format_c_comment(get_doc(value), indent=8))

        attr_id = snake_to_upper_camelcase(value["name"])
        offset = value["offset"]
        csharp_type = gen_csharp_type(value)

        f.write(
            "        public static void Set%s(%s value) { " % (attr_id, csharp_type)
        )
        if value["data_type"] == "enum":
            f.write(" Wam.SetAttribute(%d, Wam.EnumToLong(value)); " % (offset))
        else:
            f.write(" Wam.SetAttribute(%d, value); " % (offset))
        f.write(" }\n")

    f.write("    }\n")  # partial static class Wam

    f.write("}\n\n")  # namespace WhatsApp

    events_header = """\
namespace WhatsApp.Events
{
    // TODO: move definition to runtime
    public abstract class WamEvent
    {
        // log event (without sampling)
        public virtual void SaveEvent() {
            this.SaveEventWithWeight(1);
        }

        // log event with 1/interval sampling rate
        public virtual void SaveEventSampled(uint interval) {
            if (Wam.UniformRandom(interval) != 0) return;  // event not in sample

            this.SaveEventWithWeight(interval);
        }

        // log event (without sampling) and tell the server to retain it for all
        // users (normally, server would store data only for a subset of users)
        public virtual void SaveEventKeepForAllUsers() {
            this.SaveEventWithWeight(0);
        }

        // ADVANCED -- use when sampling is handled outside of Wam to provide
        // correct sampling weight (sampling rate = 1/weight)
        public virtual void SaveEventWithWeight(uint weight) {
            Wam.LogEvent(this, weight);
        }

        public abstract uint GetCode();
        public abstract void SerializeFields();
    }\n
"""
    f.write(events_header)

    # generate C# classes and serialization stubs for events
    for event in schema.events:
        f.write(format_c_comment(get_doc(event), indent=4))

        event_id = snake_to_upper_camelcase(event["name"])
        event_code = gen_event_code(event)

        f.write("    public class %s : WamEvent\n    {\n" % event_id)
        # f.write("        public readonly int code = %d;\n", % event_code)

        event_fields = event.get("field", [])

        # generate C# fields that correspond to the event definition
        for field in event_fields:
            field_id = snake_to_camelcase(field["name"])
            value = field["value_def"]
            csharp_type = gen_csharp_type(value)

            comment = (
                "("
                + format_data_type(value, enum_prefix="wam_enum_", include_units=False)
                + ") "
                + get_doc(value)
            )
            f.write(format_c_comment(comment, indent=8))

            f.write("        public %s %s = null;\n" % (csharp_type, field_id))

        # reset event
        f.write("\n")
        f.write("        public void Reset()\n        {\n")
        for field in event_fields:
            field_id = snake_to_camelcase(field["name"])
            f.write("            this.%s = null;\n" % field_id)
        f.write("        }\n")  # ResetEvent()

        # get code
        f.write("\n")
        f.write("        public override uint GetCode()\n        {\n")
        f.write("            return %d;\n" % event_code)
        f.write("        }\n")  # GetCode()

        # generate serializer
        f.write("\n")
        f.write("        public override void SerializeFields()\n        {\n")
        for field in event_fields:
            field_id = snake_to_camelcase(field["name"])
            value = field["value_def"]
            if value["data_type"] == "enum":
                f.write(
                    "            Wam.MaybeSerializeField(%d, Wam.EnumToLong(this.%s));\n"
                    % (field["field_code"], field_id)
                )
            else:
                f.write(
                    "            Wam.MaybeSerializeField(%d, this.%s);\n"
                    % (field["field_code"], field_id)
                )
        f.write("        }\n")  # SerializeFields()

        f.write("    }\n")  # Event

    f.write("}\n")  # namespace WhatsApp.Events


def gen_stubs(schema, schema_version, output_dir):

    join = os.path.join

    def get_output_dir(path, *paths):
        return ensure_dir(output_dir, path, *paths)

    with_open_file(
        join(get_output_dir("erlang"), "wa_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(
            f,
            schema,
            properties=[("server", "wa"), ("server_side", True)],
            remove_server_side=False,
            generate_code_constants=True,
        ),
    )
    with_open_file(
        join(get_output_dir("erlang"), "wamd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(
            f,
            schema,
            properties=[("server", "wamd"), ("server_side", True)],
            remove_server_side=False,
            generate_code_constants=True,
        ),
    )
    with_open_file(
        join(get_output_dir("erlang"), "grpd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "grpd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "ac2d_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "ac2d")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "chatd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "chatd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "usrd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "usrd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "payd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "payd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "webd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "webd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "offd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "offd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "presd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "presd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "pshd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "pshd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "bizd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "bizd")]),
    )
    # deprecated
    # with_open_file('erlang/mmd_wam_stubs.hrl', lambda f: gen_erlang_stubs(f, schema, properties=[('server', 'mmd')]))
    with_open_file(
        join(get_output_dir("erlang"), "regd_wam_stubs.hrl"),
        lambda f: gen_erlang_stubs(f, schema, properties=[("server", "regd")]),
    )
    with_open_file(
        join(get_output_dir("erlang"), "regd_wam_stubs.erl"),
        lambda f: gen_erlang_consts(
            f,
            schema,
            modname="regd_wam_stubs",
            hrl_filename="regd_wam_stubs.hrl",
            properties=[("server", "regd")],
        ),
    )

    webclient_schema = gen_client_schema(schema, properties=[("platform", "webclient")])
    with_open_file(
        join(get_output_dir("webclient"), "metric.js"),
        lambda f: gen_js(f, webclient_schema),
    )

    # used only for testing C implementation
    common_schema = gen_client_schema(schema, properties=[("platform", "iphone")])
    with_open_file(
        join(get_output_dir("c"), "wam_stubs.h"),
        lambda f: gen_c_h(f, common_schema, schema_version),
    )

    android_schema = gen_client_schema(schema, properties=[("platform", "android")])
    gen_android_stubs(get_output_dir("android"), android_schema)
    gen_bloks_stubs(get_output_dir("bloks", "fieldstats"), android_schema)
    gen_bloks_www_stubs(get_output_dir("blokswww", "fieldstats"), android_schema)

    iphone_schema = gen_client_schema(schema, properties=[("platform", "iphone")])
    with_open_file(
        join(get_output_dir("iphone"), "wam_stubs.h"),
        lambda f: gen_c_h(f, iphone_schema, schema_version),
    )
    with_open_file(
        join(get_output_dir("iphone"), "WamStubs.h"),
        lambda f: gen_objc_h(f, iphone_schema),
    )
    with_open_file(
        join(get_output_dir("iphone"), "WamStubs.m"),
        lambda f: gen_objc_m(f, iphone_schema, schema_version),
    )

    kaios_schema = gen_client_schema(schema, properties=[("platform", "kaios")])
    with_open_file(
        join(get_output_dir("kaios"), "metrics.js"),
        lambda f: gen_kaios_js(f, kaios_schema),
    )
    with_open_file(
        join(get_output_dir("kaios"), "wam.json"),
        lambda f: gen_kaios_meta_json(f, kaios_schema),
    )

    ent_schema = gen_client_schema(schema, properties=[("platform", "ent")])
    with_open_file(
        join(get_output_dir("ent"), "wam_stubs.h"),
        lambda f: gen_c_h(f, ent_schema, schema_version),
    )

    wp_schema = gen_client_schema(schema, properties=[("platform", "wp")])
    with_open_file(
        join(get_output_dir("wp"), "wam_stubs.h"),
        lambda f: gen_c_h(f, wp_schema, schema_version),
    )
    with_open_file(
        join(get_output_dir("wp"), "WamStubs.cs"), lambda f: gen_csharp(f, wp_schema)
    )

    windows_schema = gen_client_schema(schema, properties=[("platform", "windows")])
    with_open_file(
        join(get_output_dir("windows"), "wam_stubs.h"),
        lambda f: gen_c_h(f, windows_schema, schema_version),
    )
    with_open_file(
        join(get_output_dir("windows"), "WamStubs.cs"),
        lambda f: gen_csharp(f, windows_schema),
    )

    voip_schema = gen_client_schema(schema, properties=[("platform", "voip")])
    with_open_file(
        join(get_output_dir("voip"), "wam_stubs.h"),
        lambda f: gen_c_h(f, voip_schema, schema_version),
    )

    portal_schema = gen_client_schema(schema, properties=[("platform", "portal")])
    gen_android_stubs(get_output_dir("portal"), portal_schema)

    wamsys_schema = gen_client_schema(schema, properties=[("platform", "wamsys")])
    with_open_file(
        join(get_output_dir("wamsys"), "WAMStubsInterfaces.h"),
        lambda f: gen_wamsys_interface(f, wamsys_schema, schema_version),
    )
    with_open_file(
        join(get_output_dir("wamsys", "wa_iphone"), "WAMStubsInterfacesImpl.c"),
        lambda f: gen_wamsys_wa_impl(f, wamsys_schema, schema_version, "iphone"),
    )
    with_open_file(
        join(get_output_dir("wamsys", "wa_android"), "WAMStubsInterfacesImpl.c"),
        lambda f: gen_wamsys_wa_impl(f, wamsys_schema, schema_version, "android"),
    )
    with_open_file(
        join(get_output_dir("wamsys", "stubs"), "WAMStubsInterfacesImpl.c"),
        lambda f: gen_wamsys_wa_impl(f, wamsys_schema, schema_version, "stubs"),
    )
