import pandas as pd
import requests
import json
from config import *
from typing import List, Dict, Any, Optional

def run_jixia(formal_statement: str, jixia_url: JIXIA_URL) -> Optional[requests.Response]:
    url = jixia_url
    data = {
        "code": formal_statement,
        "timeout": 60
    }
    try:
        resp = requests.post(url, json=data, timeout=60) 
        resp.raise_for_status() 
        return resp
    except requests.exceptions.RequestException as e:
        print(f"错误：调用 Jixia API 时发生网络错误: {e}")
        return None

def get_lean_term(formal_statement: str, mathlib_df: pd.DataFrame) -> Optional[List[Dict[str, Any]]]:
    """
    Args:
        formal_statement: Lean 语言编写的形式化语句字符串
        mathlib_df: 预加载并处理过的 mathlib pandas DataFrame

    Returns:
        一个包含所有匹配到的 Lean term 信息的字典列表
    """
    if mathlib_df is None:
        print("错误：mathlib DataFrame 未被成功加载，无法执行查找。")
        return None, None

    # 1. 调用 API 并获取 type_references
    print("\n--- 步骤 1: 正在调用 Jixia API 分析语句 ---")
    resp = run_jixia(formal_statement, JIXIA_URL)
    if not resp:
        print(resp.text)
        return None, None # 如果 API 调用失败，提前退出

    try:
        data = json.loads(resp.text)
        type_ref = data["bundles"][0]["symbol"]["type_references"]
        print(f"成功从 API 获取 {len(type_ref)} 个类型引用。")
        print(type_ref)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"错误：无法从 API 响应中解析 'type_references'。错误: {e}")
        print("API 返回的原始文本:", resp.text)
        return None, None

    # 2. 查找匹配的 Lean Terms
    print("\n--- 步骤 2: 正在 mathlib 数据集中查找匹配项 ---")
    found_terms_dict = {} # 使用字典以 full_name 为键，自动去重

    for ref_parts in type_ref:
        if not ref_parts:
            continue
        
        base_name = ref_parts[-1]
        lean_name = ".".join(ref_parts)
        if base_name not in formal_statement:
            continue  
        # -----------------------------------------------------------

        mask = (mathlib_df['full_name'] == lean_name)
        
        potential_matches = mathlib_df[mask]

        if not potential_matches.empty:
            for index, row in potential_matches.iterrows():
                full_name = row['full_name']
                if full_name not in found_terms_dict:
                    print(f"  - 找到匹配: '{lean_name}' -> '{full_name}'")
                    found_terms_dict[full_name] = row.to_dict()

    if not found_terms_dict:
        print("未找到任何匹配的 Lean terms。")
        return type_ref, []
        
    return type_ref, list(found_terms_dict.values())