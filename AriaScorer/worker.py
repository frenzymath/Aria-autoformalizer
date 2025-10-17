from config import *
from prompts import SUBTASK_DECOMPOSITION_PROMPT, NLI_JUDGE_PROMPT, ALL_EXAMPLES, NLI_JUDGE_PROMPT_NO_JIXIA
import re
from utils import compute_fuzzy_score, _extract_ratings_from_output, call_llm_gemini
import json

class SubtaskDecomposer:
    def __init__(self, model_name_or_path=None):
        pass  

    def decompose(self, nl_problem: str) -> str:
        prompt = SUBTASK_DECOMPOSITION_PROMPT.format(problem=nl_problem)
        output = call_llm_gemini(prompt, max_tokens=MAX_NEW_TOKENS_SUBTASK)
        print(output)

        # 删除 <think>...</think> 模块
        output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL)

        tag = "[Conditions and Conclusions]"
        parts = output.split(tag)

        if len(parts) >= 2:
            output = tag + parts[-1]
        return output.strip()

class NLFLScorer:
    def __init__(self):
        self.model = self  
        self.last_raw_output = ""
        self.final_ouput = ""

    def generate_text(self, prompt: str) -> str:
        output = call_llm_gemini(prompt, max_tokens=MAX_NEW_TOKENS_NLI)
        self.last_raw_output = output
        
        final_ouput = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL)
        self.final_ouput = final_ouput
        return output, final_ouput

    def judge(self, 
                math_conditions: str, 
                formal_statement: str, 
                informal_statement: str = None,
                type_ref_lst: str = None,
                ls_results: str = None
                ) -> str:
        if type_ref_lst is None and ls_results is None:
            prompt = NLI_JUDGE_PROMPT_NO_JIXIA.format(
                informal_statement=informal_statement,
                math_conditions=math_conditions,
                formal_statement=formal_statement,
                few_shots_example=ALL_EXAMPLES)
        else:    
            prompt = NLI_JUDGE_PROMPT.format(
                informal_statement=informal_statement,
                math_conditions=math_conditions,
                formal_statement=formal_statement,
                few_shots_example=ALL_EXAMPLES,
                type_ref_lst=type_ref_lst,
                ls_results=ls_results
                )
        output_raw, output_final = self.model.generate_text(prompt)
        print("=== LLM raw output ===")
        print(output_raw)

        ratings = _extract_ratings_from_output(output_final)

        if not ratings:
            return json.dumps({"score": None, "grade": "UNKNOWN"}, ensure_ascii=False)

        score = compute_fuzzy_score(ratings)

        return score