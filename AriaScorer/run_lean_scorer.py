from scorer import lean_score
import pandas as pd
import argparse

try:
    print("正在从 Hugging Face Hub 加载 mathlib 数据集 ...")
    # 加载原始数据集
    df_mathlib = pd.read_json("hf://datasets/FrenzyMath/mathlib_informal_v4.19.0/data.jsonl", lines=True)
    
    # 预处理：创建一个新的列 'full_name'，其中包含点分隔的完整名称字符串。
    df_mathlib['full_name'] = df_mathlib['name'].apply('.'.join)
    print("数据集加载并预处理成功！")

except Exception as e:
    print(f"无法加载 mathlib 数据集。请检查网络连接和 huggingface-cli 登录状态。错误: {e}")
    df_mathlib = None

if __name__ == "__main__":
    # input_file = "example/test.json"
    
    # output_file = "example/test_result"
    
    parser = argparse.ArgumentParser(description="Start AriaScorer")
    parser.add_argument("input_file", type=str, help="Input Path")
    parser.add_argument("output_file", type=str, help="Output Path")
    args = parser.parse_args()
    lean_score(args.input_file, df_mathlib, args.output_file)
    print(f"\n✅ Finished scoring. Output saved to: {args.output_file}")