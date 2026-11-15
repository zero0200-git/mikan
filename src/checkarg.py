from collections.abc import Callable
from types import UnionType
from typing import Any, Union, get_args, get_origin

def checkArg(arg:dict) -> dict:
    data = {
        "input": {},
        "context": [
            {
                "var": "text",
                "type": str,
                "def": "default",
                "req": False
            }
        ]
    }
    out = {"status":"", "data":{}}
    def err(r):
        out["status"] = "failed"
        out["data"]["msg"] = r
        return out
    def scs(r,d):
        out["status"] = "success"
        out["data"]["msg"] = r
        out["data"]["normal"] = d
        return out
    def checkType(val, expected):
        if expected is Any: return True
        origin = get_origin(expected)
        args = get_args(expected)

        if origin is None:
            return isinstance(val, expected)

        if origin is Union or origin is UnionType:
            return any(checkType(val, a) for a in args)

        if isinstance(val, origin) is not True:
            return False

        if origin is list and len(args) > 0:
            return all(checkType(item, args[0]) for item in val)

        if origin is dict and len(args) == 2:
            return all(checkType(k, args[0]) and checkType(val[k], args[1]) for k in val)

        if origin is tuple and len(args) > 0:
            if len(args) == 2 and args[1] is Ellipsis:
                return all(checkType(item, args[0]) for item in val)
            if len(val) != len(args): return False
            return all(checkType(item, a) for item, a in zip(val, args))

        return True

    if isinstance(arg, dict) is not True: return err("[checkArg] function argument not dict")
    if ("input" in arg and "context" in arg) is not True: return err("[checkArg] input or context not in argument")
    if isinstance(arg["context"], list) is not True: return err("[checkArg] context not an list")
    if isinstance(arg["input"], dict) is not True: arg["input"] = {}

    input = arg["input"]
    inputOut = {}
    context = arg["context"]

    for v in context:
        if isinstance(v, dict) is not True: return err("[checkArg] value include context is not a dict")
        if ("var" in v and "type" in v) is not True: return err("[checkArg] value include context is not complete")

        v["req"] = bool(v["req"]) if "req" in v else False
        baseType = get_origin(v["type"]) or v["type"]

        if (v["req"]) is not True:
            if v["var"] in input:
                if checkType(input[v["var"]], v["type"]) is not True:
                    return err(f"{v["var"]} is wrong type (require {str(v["type"])} but received {type(input[v["var"]])})")
                inputOut[v["var"]] = input[v["var"]]
            else:
                if baseType == list:
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = []

                if baseType == tuple:
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = ()

                if(baseType == dict):
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = {}

                if(baseType == str):
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = ""

                if(baseType == int):
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = 0

                if(baseType == float):
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = 0.0

                if(baseType == bool):
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = False

                if(baseType == Callable):
                    if "def" in v and checkType(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
                    else: inputOut[v["var"]] = lambda:""
        else:
            try:
                if checkType(input[v["var"]], v["type"]) is not True:
                    return err(f"{v["var"]} is wrong type (require {str(v["type"])} but received {type(input[v["var"]])})")

                if baseType == list and len(input[v["var"]]) <= 0:
                    return err(f"{v["var"]} is require but received emply list")
                if baseType == tuple and len(input[v["var"]]) <= 0:
                    return err(f"{v["var"]} is require but received emply tuple")
                if baseType == dict and len(input[v["var"]]) <= 0:
                    return err(f"{v["var"]} is require but received emply dict")
                if baseType == str and len(input[v["var"]]) <= 0:
                    return err(f"{v["var"]} is require but received emply str")
                inputOut[v["var"]] = input[v["var"]]
            except KeyError:
                return err(f"{v["var"]} is require")

    return scs("[checkArg] sucess",inputOut)