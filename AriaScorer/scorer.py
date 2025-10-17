import json
from worker import SubtaskDecomposer, NLFLScorer
from lean_term import get_lean_term
from config import *
import os
import pandas as pd

def lean_score(json_path: str, mathlib_df: pd.DataFrame, output_path: str = None):
    with open(json_path, 'r') as f:
        data = json.load(f)

    decomposer = SubtaskDecomposer()
    scorer = NLFLScorer()

    # 输出
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
        f.write("")  # 清空内容

    for i, item in enumerate(data):
        print(f"\nProcessing {i+1}/{len(data)}")
        nl = item['informal_statement']
        fl = item['agent_output']

        type_ref_lst, ls_results = get_lean_term(fl, mathlib_df)
        if type_ref_lst is None and ls_results is None:
            item['lean_build'] = 'Failed'
        else:
            item['lean_build'] = 'Succeed'

        # 1. 拆分子任务
        math_conditions = decomposer.decompose(nl)

        # 2. 调用 LLM 判断每个子任务其是否匹配 formal 版本
        score = scorer.judge(math_conditions, fl, nl, type_ref_lst, ls_results)
        print(f"Score: {score}")

        # 记录输出
        with open(full_output_path, "a", encoding="utf-8") as fout:
            fout.write("=" * 100 + "\n")
            fout.write(f"Example {i+1}:\n\n")
            fout.write(f"Math Conditions:\n{math_conditions}\n\n")
            fout.write(f"Type reference list:\n\n{type_ref_lst}\n\n")
            fout.write(f"Search results:\n\n")
            if ls_results:
                for element in ls_results:
                    output_element = {
                        'name': list(element['name']),
                        'kind': element['kind'],
                        'value': element['value'],
                        'informal_name': element['informal_name'],
                        'informal_description': element['informal_description']
                    }
                    fout.write(f"{output_element}\n")
            fout.write(f"\n\nFormal Statement:\n{fl}\n\n")
            fout.write("LLM Full Output:\n")
            fout.write(scorer.last_raw_output.strip() + "\n\n")

        # 3. 聚合为 fuzzy score
        item['math_conditions'] = math_conditions
        item['lean_score'] = score
        item['pass'] = item['lean_score'] >= THRESHOLD_PASS

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)