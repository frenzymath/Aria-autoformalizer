import asyncio
import yaml
import sys
from typing import Dict, List
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
except FileNotFoundError:
    print("错误: 未找到 config.yaml 文件。请先创建并配置该文件。")
    exit()
print(CONFIG)
async def main():
    """
    主执行函数，用于搭建和运行 PocketFlow 流程。
    """
    print("✅ 配置文件加载成功。") 
    #informal_statement = "For any commutative ring R, if every prime ideal is finitely generated, then R is Noetherian."
    informal_definitions = r""""""
    informal_statement = r"""Suppose that R is a ring. If R has no nil ideal, other than {0}, then it has no nil one-sided ideal, other than {0}."""
    initial_data = {
        "informal_statement": informal_statement,
        "informal_definitions": informal_definitions
    }
    print(f"🚀 正在启动 Pocketflow 流程...") 
    print(f"--- [Start] --- \n初始陈述: {informal_statement}")

    node1_extract_keywords = KeywordExtractionNode()
    node2_formalize_definitions = DefinitionFormalizer_GoT_Node(config=CONFIG)
    node3_formalize_theorem = TheoremFormalizationNode(config=CONFIG)

    flow = AsyncFlow()

    flow.start(node1_extract_keywords) >> node2_formalize_definitions >> node3_formalize_theorem
    
    print("⏳ 正在运行 PocketFlow 流程...")
    final_shared_data = await flow.run_async(initial_data)

    final_result = final_shared_data.get("final_formal_statement", "未能生成最终结果。")
    
    print("\n--- [✨ Final Result] ---")
    print("最终的形式化Lean 4定理陈述:")
    print("```lean")
    print(final_result)
    print("```")

if __name__ == "__main__":
    print("--- 正在进入程序主入口 (`__main__`) ---")
    asyncio.run(main())
    print("--- 程序执行完毕 (`main` 函数已返回) ---")

