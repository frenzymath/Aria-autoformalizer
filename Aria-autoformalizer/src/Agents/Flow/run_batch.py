import asyncio
import yaml
import sys
import json
import argparse
from typing import Dict, List, Any, Optional

from src.Agents.Autoformalizer.nodes import (
    KeywordExtractionNode, 
    DefinitionFormalizer_GoT_Node, 
    TheoremFormalizationNode,
    DefinitionFormalizer_Ablation_Node
)
from src.PocketFlow import AsyncFlow

CONFIG = {}
try:
    with open('configs/config.yaml', 'r', encoding='utf-8') as f:
        CONFIG = yaml.safe_load(f)
    print("✅ 配置文件 'config.yaml' 加载成功。")
except FileNotFoundError:
    print("❌ 错误: 未找到 config.yaml 文件。请先创建并配置该文件。")
    exit()

async def run_formalization_pipeline(
    informal_statement: str, 
    informal_definitions: str = ""
) -> Dict[str, Any]:
    """
    对单个 informal_statement 运行完整的 PocketFlow 形式化流程。
    """
    initial_data = {
        "informal_statement": informal_statement,
        "new_definitions": informal_definitions 
    }
    task_stats_tracker = {}
    
    node1_extract_keywords = KeywordExtractionNode()
    node2_formalize_definitions = DefinitionFormalizer_GoT_Node(config=CONFIG, stats_tracker=task_stats_tracker)
    node3_formalize_theorem = TheoremFormalizationNode(config=CONFIG, stats_tracker=task_stats_tracker)

    flow = AsyncFlow()
    flow.start(node1_extract_keywords) >> node2_formalize_definitions >> node3_formalize_theorem
    
    final_shared_data = await flow.run_async(initial_data)
    final_shared_data['stats'] = task_stats_tracker
    return final_shared_data

async def main(args):
    """
    主执行函数，负责读取、并发处理和保存结果。
    """
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            tasks = [json.loads(line) for line in f if line.strip()]
        print(f"✅ 成功从 '{args.input_file}' 加载 {len(tasks)} 个任务。")
    except Exception as e:
        print(f"❌ 读取输入文件 '{args.input_file}' 时出错: {e}")
        return

    common_informal_definitions = ""
    
    print(f"🚀 准备并发处理 {len(tasks)} 个任务...")
    coroutines = []
    for task in tasks:
        informal_statement = task.get("nl_statement")
        if informal_statement:
            coroutines.append(
                run_formalization_pipeline(
                    informal_statement=informal_statement,
                    informal_definitions=common_informal_definitions
                )
            )

    #使用 asyncio.gather 并发运行所有任务
    results_data = await asyncio.gather(*coroutines, return_exceptions=True)
    
    print("✅ 所有任务并发执行完毕，正在整理结果...")
    total_stats = {
        "definition_synthesis_calls": 0,
        "theorem_generation_calls": 0
    }
    task_call_details = []
    final_results = []
    for i, task in enumerate(tasks):
        result = results_data[i]

        if isinstance(result, Exception):
            print(f"❌ 任务 #{i+1} (ID: {task.get('id', 'N/A')}) 处理失败: {result}")
            task['agent_output'] = None
            task['status'] = 'failed'
            task['error_message'] = str(result)
        else:
            if result.get("final_compilation_success"):
                task['status'] = 'success'
                print("✅ 任务处理成功，且代码编译通过。")
            else:
                task['status'] = 'failed'
                task['error_message'] = result.get("final_compilation_error", "Compilation failed with no specific error.")
                print(f"❌ 任务处理成功，但最终代码编译失败。")

            task['agent_output'] = result.get("final_formal_statement", "未能生成最终结果。")
            task['agent_generated_context'] = result.get("newly_defined_context", "")
        
            task_stats = result.get('stats', {})
            def_calls = task_stats.get('definition_synthesis_calls', 0)
            theorem_calls = task_stats.get('theorem_generation_calls', 0)

            total_stats['definition_synthesis_calls'] += def_calls
            total_stats['theorem_generation_calls'] += theorem_calls

            task_call_details.append({
                "id": task.get('id', ""),
                "informal_statement": task.get("nl_statement", ""),
                "total_calls": def_calls + theorem_calls
            })
        final_results.append(task)
    
    try:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False)
        print("\n" + "="*50)
        print(f"✨ 全部任务处理完毕！结果已保存到 '{args.output_file}'。")
    except Exception as e:
        print(f"❌ 写入输出文件 '{args.output_file}' 时出错: {e}")
        
    print("\n" + "="*50)
    print("📊 --- 批量处理总统计 ---")
    print(f"处理的总任务数: {len(tasks)}")
    print(f"总定义合成API调用次数 (含重试): {total_stats['definition_synthesis_calls']}")
    print(f"总定理生成API调用次数 (含重试): {total_stats['theorem_generation_calls']}")
    
    if task_call_details:
        task_call_details.sort(key=lambda x: x["total_calls"], reverse=True)
        
        print("\n--- 翻译次数最高的任务 Top 3 ---")
        for rank, detail in enumerate(task_call_details[:3]):
            if detail['total_calls'] > 0: # 只显示有调用的
                print(f"  #{rank + 1}: ID '{detail['id']}'")
                print(f"     总调用次数: {detail['total_calls']}")
                print(f"     问题陈述: {detail['informal_statement'][:100]}...")
            
    print("="*50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量运行 Lean 形式化 Agent。")
    parser.add_argument(
        "-i", "--input-file", 
        type=str, 
        required=True,
        help="包含 informal_statement 的输入JSON文件路径。"
    )
    parser.add_argument(
        "-o", "--output-file", 
        type=str, 
        default="results.json",
        help="用于保存结果的输出JSON文件路径 (默认为: results.json)。"
    )
    args = parser.parse_args()

    print("--- 正在进入程序主入口 (`__main__`) ---")
    asyncio.run(main(args))
    print("--- 程序执行完毕 (`main` 函数已返回) ---")