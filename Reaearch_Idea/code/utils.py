import re
import json
import copy
from typing import List, Dict, Union, Tuple, Any, Optional
from Reaearch_Idea.code.dag import returns_keys


def get_router_json(string: str):
    """专门处理router模块的JSON输出"""
    if string is None:
        return None
        
    # 清理字符串
    string = string.strip()
    # 如果是直接的JSON格式
    if string.startswith('{') and string.endswith('}'):
        return string
    return None


def get_json(string: str):
    pattern = r"```json\n(.*)\n```"
    match = re.search(pattern, string, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def is_float(string):
    pattern = r'^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$'
    return bool(re.match(pattern, string))


def escape_CLRF(string: str):
    string = string.replace('\r\n', '\n')
    return re.sub(r'(?<!\n)\n(?!\n)', '', string).strip()


def escape_underline(string: str):
    return re.sub(r'_', '\\_', string)


def escape_markdown(string: str):
    string = re.sub(r'[*_`~\[\]()#<>]+', '', string)
    return string


# temp utils function for value retrieve
def get_extremes(flag: str='max', key: str='values') -> callable:
    extremes = max if flag == 'max' else min
    def _extremes(items: Dict[str, List]) -> float:
        if not items:
            return None
        return extremes(items[key])
    return _extremes


def fl32(expression):
    pattern = r"10\s?([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)|10\^([-+]?\d+)"

    def replace(match):
        if match.group(1):
            exponent = match.group(1)
            exponent = exponent.replace('⁰', '0').replace('¹', '1').replace('²', '2').replace('³', '3') \
                                .replace('⁴', '4').replace('⁵', '5').replace('⁶', '6').replace('⁷', '7') \
                                .replace('⁸', '8').replace('⁹', '9').replace('⁻', '-')
            return f"10e{exponent}"
        elif match.group(2):
            exponent = match.group(2)
            return f"10e{exponent}"
    return float(re.sub(pattern, replace, expression))


def parse_values(values: List[str]) -> List[Union[Tuple, str]]:
    value_ranges = []
    logic_ranges = []

    if not values:
        return value_ranges, logic_ranges
    
    for range in values:
        if range == "-":
            continue
        elif "-" in range:
            try:
                start, end = range.split("-")
                start = fl32(start) if start else None
                end = fl32(end) if end else None
                value_ranges.append((start, end))
            except ValueError:
                print(f"Invalid value range: {range}")
        elif is_float(range):
            start = fl32(range)
            value_ranges.append((start, start))
        elif range.lower() in ["max", "min"]:
            logic_ranges.append(range.lower())
        else:
            print(f"Invalid value range: {range}")
    return value_ranges, logic_ranges

@returns_keys(keyvalues=List[Dict], keywords=List[str], keyvalues_data=List[Dict], embrace_values=List[bool])
def extract_keyvalues(text: Optional[str] = None) -> Tuple[List[Dict], List[bool]]:
    print(text)
    text = get_json(text)
    keyvalues_data = json.loads(text)

    if not keyvalues_data:
        print("No keyvalues data found")
        return [], []
    if not isinstance(keyvalues_data, List):
        print("Invalid keyvalues data")
        return [], []
    
    keyvalues = []
    embrace_values = []
    for item in keyvalues_data:
        if not item:
            continue
        if not isinstance(item, Dict):
            continue

        if not item.get("keyword"):
            continue

        new_item = copy.deepcopy(item)
        for key in ["keyword", "value", "unit"]:
            if isinstance(item.get(key), str):
                new_item[key] = [item[key]]
            elif item.get(key) is None:
                new_item[key] = []
            new_item[key] = [x for x in new_item[key] if x.strip() != ""]
        keyvalues.append(new_item)
        embrace_values.append(bool(new_item["value"]))

    keyvalue_pairs = [kv for kv, embrace in zip(keyvalues, embrace_values) if embrace]
    keywords = [kv["keyword"] for kv in keyvalues]
    
    
    return {
        "keyvalue_pairs": keyvalue_pairs,
        "keywords": keywords,  # ✅ 你要给 BM25Retriever 的字段
        "keyvalues": keyvalues,
        "embrace_values": embrace_values
    }


    # return keyvalue_pairs, keywords, keyvalues, embrace_values修改了return的形式，从4个值变为了一个dict


# temp utils function for database operation
def union_all(operations: List[str]):
    operations = filter_nulls(operations)
    return "UNION ALL\n".join(operations)


def AND(conditions: List):
    conditions = filter_nulls(conditions)
    return " AND ".join(conditions)


def OR(conditions: List):
    conditions = filter_nulls(conditions)
    return " OR ".join(conditions)


def brk(condition: str):
    if condition == "":
        return condition
    return f"({condition})"


def filter_nulls(conditions: List[str]):
    return [condition for condition in conditions if condition]


def range_patterns(start, end, column_name = ""):
    if not column_name == "":
        column_name += " "

    if not (start is None or end is None):
        return f"{column_name}BETWEEN %s AND %s", [start, end]
    elif end is None:
        return f"{column_name}>= %s", [start]
    elif start is None:
        return f"{column_name}<= %s", [end]
    else:
        raise ValueError("Invalid value range")


def similar_patterns(value, wildcard='all', column_name = ""):
    if not column_name == "":
        column_name += " "

    if wildcard == 'all':
        return f"{column_name}LIKE %s", [f"%{value}%"]
    elif wildcard == 'prefix':
        return f"{column_name}LIKE %s", [f"{value}%"]
    elif wildcard == 'suffix':
        return f"{column_name}LIKE %s", [f"%{value}"]
    else:
        raise ValueError("Invalid wildcard type")
