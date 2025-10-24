import json
from worker import SubtaskDecomposer, NLFLScorer
from lean_term import get_lean_term
from config import *
import os
import pandas as pd
import concurrent.futures 
from typing import Dict, Any, List, Tuple

def process_item(
    item: Dict[str, Any], 
    index: int, 
    mathlib_df: pd.DataFrame
) -> Tuple[int, Dict[str, Any], str]:
    
    print(f"--- 启动任务 {index + 1} ---")
    
    # 为每个线程创建独立的实例以保证线程安全
    decomposer = SubtaskDecomposer()
    scorer = NLFLScorer()

    nl = item['informal_statement']
    fl = item['agent_output']

    try:
        type_ref_lst, ls_results = get_lean_term(fl, mathlib_df)
        if type_ref_lst is None and ls_results is None:
            item['lean_build'] = 'Failed'
        else:
            item['lean_build'] = 'Succeed'

        # 1. 拆分子任务
        math_conditions = decomposer.decompose(nl)

        # 2. 调用 LLM 判断
        score = scorer.judge(math_conditions, fl, nl, type_ref_lst, ls_results)
        print(f"✅ 任务 {index + 1} 完成, Score: {score}")

        # 3. 聚合为 fuzzy score
        item['math_conditions'] = math_conditions
        item['lean_score'] = score
        item['pass'] = item['lean_score'] >= THRESHOLD_PASS

        # 准备日志输出，而不是直接写入文件
        log_content = "=" * 100 + "\n"
        log_content += f"Example {index + 1}:\n\n"
        log_content += f"Math Conditions:\n{math_conditions}\n\n"
        log_content += f"Type reference list:\n\n{type_ref_lst}\n\n"
        log_content += f"Search results:\n\n"
        if ls_results:
            for element in ls_results:
                output_element = {
                    'name': list(element['name']),
                    'kind': element['kind'],
                    'value': element['value'],
                    'informal_name': element['informal_name'],
                    'informal_description': element['informal_description']
                }
                log_content += f"{output_element}\n"
        log_content += f"\n\nFormal Statement:\n{fl}\n\n"
        log_content += "LLM Full Output:\n"
        log_content += scorer.last_raw_output.strip() + "\n\n"

        return index, item, log_content

    except Exception as e:
        print(f"任务 {index + 1} 失败: {e}")
        error_log = f"ERROR processing Example {index + 1}:\n{e}\n\nFormal Statement:\n{fl}\n\n"
        item['lean_build'] = 'Failed'
        item['lean_score'] = json.dumps({"score": None, "grade": "ERROR"}, ensure_ascii=False)
        item['pass'] = False
        return index, item, error_log

def lean_score(json_path: str, mathlib_df: pd.DataFrame, output_path: str = None, max_workers: int = 10):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # --- 输出路径设置 ---
    if not output_path:
        output_path = json_path.replace('.json', '_lean_score.json')

    output_dir = os.path.dirname(output_path)
    output_base = os.path.splitext(os.path.basename(output_path))[0]
    full_output_path = os.path.join(output_dir, output_base + "_full_output.txt")

    if not output_path.endswith('.json'):
            output_path += '.json'
            
    os.makedirs(output_dir, exist_ok=True)    
    
    # === 清空原来的 full_output 文件 ===
    with open(full_output_path, "w", encoding="utf-8") as f:
        f.write(f"启动并行处理，共 {len(data)} 个任务，使用 {max_workers} 个 workers...\n\n")

    
    # --- 并行处理 ---
    temp_results = [] 
    
    print(f"\nProcessing {len(data)} items using up to {max_workers} workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_item, item, i, mathlib_df): i 
            for i, item in enumerate(data)
        }
        
        # 实时收集完成的结果
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                temp_results.append(result)
            except Exception as e:
                item_index = futures[future]
                print(f"任务 {item_index + 1} 发生严重错误: {e}")
                error_item = data[item_index]
                error_item['lean_score'] = json.dumps({"score": None, "grade": "CRITICAL_ERROR"}, ensure_ascii=False)
                error_log = f"CRITICAL ERROR on Example {item_index + 1}:\n{e}\n\n"
                temp_results.append((item_index, error_item, error_log))

    # --- 按原始顺序 ---
    temp_results.sort(key=lambda x: x[0])

    # --- 统一写入结果 ---
    final_data_to_save = []
    with open(full_output_path, "a", encoding="utf-8") as fout:
        for index, updated_item, log_content in temp_results:
            final_data_to_save.append(updated_item)
            fout.write(log_content) # 按顺序写入日志

    # 写入最终的 JSON 结果
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_data_to_save, f, indent=2, ensure_ascii=False)