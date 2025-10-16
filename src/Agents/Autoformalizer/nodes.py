import asyncio
import yaml
from typing import Dict, List, Optional
import sys
from src.PocketFlow import AsyncFlow, AsyncNode
import src.tools as tools
from src.Agents.GoT.orchestrator import GoT_Orchestrator
from src.LeanSearch.client import std_search_remote

CONFIG = {}
try:
    with open('configs/config.yaml', 'r', encoding='utf-8') as f:
        CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    print("错误: 未找到 config.yaml 文件。请先创建并配置该文件。")
    exit()

class KeywordExtractionNode(AsyncNode):
    async def prep_async(self, shared_data: Dict):
        print("\n--- [Node 1/3] Keyword Extraction ---")
        sys.stdout.flush()
        return shared_data.get("informal_statement")

    async def exec_async(self, informal_statement: str) -> List[str]:
        try:
            # Replace your existing prompt with this one for the best results
            prompt = f"""
You are an expert in formal mathematics, acting as a search query generator for the Mathlib library. Your task is to extract the most specific and complete mathematical concepts from a given statement.

---
**RULES TO FOLLOW:**

1.  **Extract Concepts, Not Single Words:** Do NOT extract single, isolated adjectives or nouns like "prime", "ring", "ideal", or "finitely generated".
2.  **Combine Words into Phrases:** Always combine adjectives with the nouns they describe to form a complete concept. For example, "prime" and "ideal" should be combined into "prime ideal".
3.  **Do Not Rephrase the Theorem:** Your keywords should be the *concepts* used in the theorem, not a natural language summary or rephrasing of the entire theorem's logic. Avoid phrases with verbs like "implies", "is", "are", "proves that".
4.  **Extract Core Concepts / Avoid Composites**: Extract the core, foundational mathematical concepts. If a longer phrase is a composite description built upon a simpler concept (e.g., "square of...", "set of..."), extract only the simpler, core concept.
For example: From the phrase "the square of the irrelevant maximal ideal", you should only extract 'irrelevant maximal ideal'.
AVOID: Extracting the longer, composite phrase 'square of the irrelevant maximal ideal'.
5.  **Output Format:** Your final output MUST be a single, valid JSON object with one key, "keywords", whose value is a list of the extracted string keywords.

---
**EXAMPLE**

**Informal Statement:**
"For any commutative ring R, if every prime ideal is finitely generated, then R is Noetherian."

**Correct Output (JSON):**
{{"keywords": ["commutative ring", "prime ideal", "finitely generated ideal", "Noetherian ring"]}}

**Incorrect Keywords to AVOID:**
["commutative", "prime", "ideal", "finitely generated", "every prime ideal is finitely generated"]
---

**YOUR TASK**

**Informal Statement:**
"{informal_statement}"

**JSON Output (provide only the JSON object):**
"""
            print("  [节点1内部] 准备调用 LLM API...") # 新增日志

            response_json = await tools.llm_with_strict_format(
                msgs=[{"role": "user", "content": prompt}],
                config=CONFIG["llm"]["formalizer"]
            )
        
            print("  [节点1内部] LLM API 调用成功。") # 新增日志
            keywords = response_json.get("keywords", [])
            print(f"  [节点1内部] 提取出的关键词: {keywords}")
            return keywords

        except Exception as e:
            print(f"❌❌❌ 在 KeywordExtractionNode 中发生致命错误: {e}")
            import traceback
            traceback.print_exc()  # 这会打印出完整的错误堆栈信息
            return [] # 返回一个空列表，避免流程中断

    async def post_async(self, shared_data: Dict, prep_res, keywords: List[str]):
        shared_data["keywords"] = keywords
        
class DefinitionFormalizer_GoT_Node(AsyncNode):
    def __init__(self, config: Dict, stats_tracker: Optional[Dict] = None):
        super().__init__()
        self.config = config
        self.stats_tracker = stats_tracker

    async def prep_async(self, shared_data: Dict) -> Dict:
        print("\n--- [Node 2/3] Definitional Graph-of-Thoughts ---")
        return {
            "keywords": shared_data.get("keywords", []),
            "informal_definitions": shared_data.get("informal_definitions", ""),
            "informal_statement": shared_data.get("informal_statement", "")
        }

    async def exec_async(self, got_input: Dict) -> str:
        keywords = got_input.get("keywords", [])
        informal_definitions = got_input.get("informal_definitions", "")
        informal_context = got_input.get("informal_statement", "")
        
        if not keywords:
            print("没有关键词需要进行定义形式化。")
            return ""
        synthesis_cache = {}

        newly_defined_code = []
        for keyword in keywords:
            got_orchestrator = GoT_Orchestrator(self.config, synthesis_cache=synthesis_cache, stats_tracker=self.stats_tracker)
            
            formal_code = await got_orchestrator.run(
                target_concept=keyword, 
                informal_context=informal_definitions
            )
            
            if formal_code and not formal_code.strip().startswith("/*"):
                newly_defined_code.append(
                    f"-- [Auto-Generated Definition for '{keyword}']\n{formal_code}"
                )
        
        return "\n\n".join(newly_defined_code)
    
    async def post_async(self, shared_data: Dict, prep_result: Dict, exec_result: str) -> str:
        shared_data["newly_defined_context"] = exec_result
        return None

        

class TheoremFormalizationNode(AsyncNode):
    """节点三：结合所有上下文，生成最终的定理陈述。"""
    def __init__(self, config: Dict, stats_tracker: Optional[Dict] = None):
        super().__init__()
        self.config = config
        self.stats_tracker = stats_tracker

    async def prep_async(self, shared_data: Dict):
        print("\n--- [Node 3/3] Final Theorem Formalization ---")
        
        return shared_data

    async def exec_async(self, shared_data: Dict) -> str:
        initial_prompt = f"""
You are a meticulous expert in Lean 4 and `mathlib4`. Your primary goal is to translate informal mathematical statements into **correct, idiomatic, and compilable** Lean 4 code that seamlessly integrates with the existing Mathlib library.

Before generating the final code, you MUST follow a structured thought process in five steps:

1.  **Deconstruct**: Break down the informal statement into its core mathematical components (e.g., objects, assumptions, conclusion).
2.  **Identify Mathlib Components**: List the key Mathlib definitions, theorems, and notations that are necessary to formalize each component. Guessing is not allowed; refer to known Mathlib APIs. For example, 'integral domain' corresponds to `[IsDomain R]`, 'finitely generated module' to `[Module.Finite R M]`.
3.  **Plan the Formal Statement**: Outline the structure of the final theorem. This includes defining the types (e.g., `R M : Type*`), typeclasses (e.g., `[CommRing R]`), variables, hypotheses, and the goal.
4.  **Generate Final Code**: Based on the plan, write the complete, compilable Lean 4 code.
5.  Do not generate `variable` declarations that are irrelevant to the final theorem statement. For a single theorem, prefer placing all variables and hypotheses directly in the `theorem`'s signature instead of using a global `variable` block.

**Context (Newly Generated Definitions):**
---
{shared_data.get("newly_defined_context", "# No new definitions were needed.")}
---

**Informal Theorem to Formalize:**
"{shared_data.get("informal_statement")}"

**Final Lean Theorem Statement:**
Caution: Don't generate explicit header like 'import Mathlib.RingTheory.Noetherian'. Use 'import Mathlib'. **Crucially, you must NOT write the proof.** Your only goal is to state the theorem correctly. The proof block must be replaced with the `sorry` keyword.
"""
        print(initial_prompt)
        print("正在调用 LLM 生成最终的定理陈述...")
        

        result = await tools.stat_generate_and_verify_loop(
            initial_prompt=initial_prompt,
            config=self.config,
            max_retries=16,
            stats_tracker=self.stats_tracker,
            counter_key="theorem_generation_calls"
        )

        return result

    async def post_async(self, shared_data: Dict, prep_res, verification_result: Dict):
        """
        Updates shared_data with the final formalized theorem.
        Returns None as this is the final node in the flow.
        """
        shared_data["final_formal_statement"] = verification_result.get("code")
        shared_data["final_compilation_success"] = verification_result.get("success")
        shared_data["final_compilation_error"] = verification_result.get("error")
        # Explicitly return None for clarity and consistency.
        return None
        
class DefinitionFormalizer_Ablation_Node(AsyncNode):
    """
    [Ablation Version: w/o GoT]
    This node now performs a "flat" RAG operation. It retrieves definitions
    for all keywords simultaneously and concatenates them without structured planning.
    """
    def __init__(self, config: Dict, stats_tracker: Optional[Dict] = None):
        super().__init__()
        self.config = config
        self.stats_tracker = stats_tracker

    async def prep_async(self, shared_data: Dict) -> Dict:
        # The title is changed to reflect its new role in the ablation study
        print("\n--- [Node 2/3 (Ablation w/o GoT)] Flat RAG Context Building ---")
        return {
            "keywords": shared_data.get("keywords", []),
        }

    async def ground_single_concept(self, concept_name: str) -> str | None:
        """
        A helper function to ground a single concept using the Orchestrator's utility.
        This simulates the RAG part of the agent for one concept.
        """
        # We instantiate a temporary orchestrator just to use its grounding method.
        # This is a way to reuse the grounding logic without invoking the GoT planning.
        orchestrator = GoT_Orchestrator(self.config)
        node = orchestrator.graph.add_concept(concept_name)
        
        if await orchestrator.ground_in_mathlib(node):
            return node.formal_code
        return None

    async def exec_async(self, got_input: Dict) -> str:
        keywords = got_input.get("keywords", [])
        
        if not keywords:
            print("  No keywords to retrieve definitions for.")
            return ""

        print(f"  Retrieving definitions for {len(keywords)} keywords in a single batch (no GoT planning)...")

        # Create a list of concurrent grounding tasks for all keywords
        grounding_tasks = [self.ground_single_concept(kw) for kw in keywords]
        
        # Run all grounding tasks concurrently
        grounded_codes = await asyncio.gather(*grounding_tasks)

        # Concatenate all successfully found definitions into one large context block
        context_code = []
        for keyword, code in zip(keywords, grounded_codes):
            if code:
                context_code.append(f"-- [Retrieved Definition for '{keyword}']\n{code}")
        
        print(f"  Successfully retrieved {len(context_code)} definitions.")
        return "\n\n".join(context_code)
    
    async def post_async(self, shared_data: Dict, prep_result: Dict, exec_result: str) -> str:
        # This part remains the same: it provides the context for the final theorem formalization.
        shared_data["newly_defined_context"] = exec_result
        return None
