# src/Agent/GoT/orchestrator.py

import asyncio
from typing import Dict, List, Optional


from .graph import ConceptNode, DependencyGraph
import src.tools as tools
from src.LeanSearch.client import std_search_remote


class GoT_Orchestrator:
    """
    核心调度器：GoT Agent。
    负责动态构建和遍历概念依赖图，以生成新的形式化定义。
    """
    def __init__(self, config: Dict, synthesis_cache: Optional[Dict[str, str]] = None, stats_tracker: Optional[Dict] = None):
        self.config = config
        self.graph = DependencyGraph()
        self.synthesis_cache = synthesis_cache if synthesis_cache is not None else {}
        self.stats_tracker = stats_tracker
        self.enable_rag = self.config.get("enable_rag", True)

    async def expand_dependencies(self, node: ConceptNode):
        """(Top-Down) 使用 LLM 查找一个概念的子级依赖。"""
        print(f"🧠 Expanding dependencies for '{node.name}'...")

        prompt_template = f"""
You are an expert mathematician and a specialist in formal mathematics, specifically Lean 4 and its library, mathlib4. Your task is to deconstruct a given mathematical concept into its immediate, foundational prerequisite concepts.

The goal is to produce a list of terms that are themselves canonical, searchable definitions. I will provide you with examples of correct deconstruction before giving you the final task.

---
**Example 1:**
- **Input Concept:** "Ring Homomorphism"
- **Correct Output:** {{"dependencies": ["ring", "group homomorphism"]}}

**Example 2:**
- **Input Concept:** "Topological Manifold"
- **Correct Output:** {{"dependencies": ["topological space", "locally Euclidean space"]}}

**Example 3:**
- **Input Concept:** "Finitely Generated Prime Ideal"
- **Correct Output:** {{"dependencies": ["finitely generated ideal", "prime ideal"]}}

**Example 4 (What to avoid):**
- **Input Concept:** "Prime Ideal"
- **Incorrect Output:** {{"dependencies": ["definition of a commutative ring", "the property that an ideal is not the whole ring", "a condition on products of elements"]}}
---
"""
        if node.informal_description:
            task_prompt = f"""
**Now, perform the task based on the following informal definition.**

**Your primary instruction is to determine if the provided definition is consistent with the concept name.**
- **If they are consistent**, you will extract dependencies directly from the **informal definition**.
- **If they are NOT consistent**, you must **IGNORE** the provided definition and extract dependencies based on the **concept name** alone.

**Concept Name:** "{node.name}"
**Informal Definition:** "{node.informal_description}"

**Your Task:** Read the informal definition and identify the core mathematical concepts it directly depends on. For instance, if the definition is "A group homomorphism is a function between two groups that preserves the group structure", the dependencies are "group" and "function".
"""
        else:
            task_prompt = f"""
**Now, perform the task for the following concept based on its name.**
Note: Regular Local Ring should be destructed as ["Noetherian ring", "local ring", "krull dimension of a ring", "cotangent space of local ring"].
**Concept to deconstruct:** "{node.name}"
"""
        final_prompt = prompt_template + task_prompt + "\n**Your output must be a single, valid JSON object with no other text or explanation.**"
        
        try:
            print(final_prompt)
            response = await tools.llm_with_strict_format(
                msgs=[{"role": "user", "content": final_prompt}], 
                config=self.config["llm"]["main_model"]
            )
            dependencies = response.get("dependencies", [])
            print(f"-> Found dependencies: {dependencies}")
            for dep in dependencies:
                self.graph.add_dependency(node.name, dep)
        except Exception as e:
            print(f"❗️ Error during dependency expansion for '{node.name}': {e}")
            node.status = "failed"
            node.error_message = str(e)

    def _format_leansearch_results_for_llm(self, search_results_json: List) -> str:
        if not search_results_json or not isinstance(search_results_json, list) or not search_results_json[0]:
            return "No results found."

        all_results_list = search_results_json[0]
        
        all_results_list.sort(key=lambda x: x.get('distance', 1.0))
        
        formatted_string = ""
        for i, item in enumerate(all_results_list[:10]):
            res = item.get("result", {})
            
            full_name = ".".join(res.get("name", []))
            kind = res.get("kind", "N/A")
            description = res.get("informal_description", res.get("docstring", "No description available."))
            
            formatted_string += f"Candidate {i+1}:\n"
            formatted_string += f"  - Name: `{full_name}`\n"
            formatted_string += f"  - Kind: `{kind}`\n"
            formatted_string += f"  - Description: {description}\n\n"
            
        return formatted_string.strip()


    async def ground_in_mathlib(self, node: ConceptNode) -> bool:
        """(Top-Down) 尝试在 mathlib 中找到一个概念的定义。"""
        if self.enable_rag:
            print(f"🔍 Grounding '{node.name}' in Mathlib via LeanSearch...")
            try:
                search_results = await std_search_remote(
                    queries=[node.name], 
                    config_path="configs/leansearch.yaml"
                )
                if not search_results:
                    print(f"-> LeanSearch returned no results for '{node.name}'.")
                    return False
            except Exception as e:
                print(f"-> LeanSearch call failed for '{node.name}': {e}")
                return False

            all_results_list = search_results[0]
            name_to_code_map = {}
            for item in all_results_list:
                res = item.get("result", {})
                full_name = ".".join(res.get("name", []))
                formal_code = tools.format_formal_statement(res)
                if full_name and formal_code:
                    name_to_code_map[full_name] = formal_code
        # --- 步骤 2: 推理 (Reason) ---
            candidates_context = self._format_leansearch_results_for_llm(search_results)
        
            reasoning_prompt = f"""
You are a meticulous expert in Lean 4 and `mathlib4`. Your task is to act as a "grounding" reasoner for a formalization agent. Your goal is to determine if a given mathematical concept has a canonical formal definition in `mathlib`, based on a list of search candidates.

**Concept to find:** "{node.name}"

**Search Candidates from `mathlib`:**
---
{candidates_context}
---

**Your Task (Follow these steps PRECISELY):**

**Step 1: Direct Match Analysis**
- First, look for a **direct, canonical definition** among the candidates. A direct match is typically a `class`, `structure`, or `def` whose name is very similar to the concept name (e.g., concept 'local ring' matches `class IsLocalRing`).
- If you find a clear, direct match, use that as your primary answer.

**Step 2: Deduction from Usage Patterns (If no direct match is found)**
- If no direct match was found in Step 1, your task is to **deduce** the canonical name by finding a **consistent usage pattern** across multiple `theorem` and `instance` candidates.
- **Analyze the signatures:** Look for a common identifier that is consistently used as a **type** or **typeclass** across multiple candidates.
- **Example:** If you are looking for "CharZero" and the search results include `instance : CharZero ℕ`, `instance : CharZero ℤ`, and `theorem my_thm [CharZero R]`, the identifier `CharZero` appears repeatedly as a typeclass. This is overwhelming evidence that the canonical definition is named `CharZero`.
- **Strict Rule:** The name you select **must** be an identifier that is explicitly present in the candidate list. Do **not** invent, combine, or guess a new name. If no single, consistent pattern emerges from the candidates, you must conclude that no confident match can be found.

**Example (Sticking to Evidence):** Suppose you are looking for "finrank" (the rank of a finite dimensional vector space) and the search results include:
  - `def Module.finrank (R M : Type*) ... : ℕ`
  - `theorem some_thm [FiniteDimensional K V] : ... ≤ Module.finrank K V`
  - `class FiniteDimensional (R M : Type*) ... : Prop`

  Even though the concept is related to `FiniteDimensional`, the only actual function found is `Module.finrank`.
  - **Correct Deduced Name:** `Module.finrank`
  - **Incorrect Guess to Avoid:** `FiniteDimensional.finrank` (This is an invention, not present in the candidates).

**Step 3: Final Decision**
- Based on your analysis from Step 1 and Step 2, determine the single best name for the concept.
- Your answer MUST be a single, valid JSON object with the following keys:
  - `"best_match"`: The full formal name of the canonical definition (e.g., "RingTheory.IsLocalRing"). If no confident match can be found through either direct matching or inference, the value must be `null`.
  - `"reasoning"`: A brief, one-sentence explanation of HOW you found the match. It must be one of the following strings: "Found a direct definition." or "Inferred from usage in instances and theorems." or "No confident match found."

**JSON Output:**
"""
        
            print(f"🧠 Asking LLM to reason about search candidates...")
            try:
                response_json = await tools.llm_with_strict_format(
                    msgs=[{"role": "user", "content": reasoning_prompt}],
                    config=self.config["llm"]["main_model"]
                )
                print(response_json)
                best_match_name = response_json.get("best_match")

                if best_match_name:
                # 找到了权威定义
                    formal_code = name_to_code_map.get(best_match_name)
                    node.status = "grounded"
                    if not formal_code:
                        node.formal_code = f"/- Definition for '{node.name}' found in Mathlib as: {best_match_name} -/"
                    else:
                        node.formal_code = f"/- Definition for '{node.name}' found in Mathlib as: {best_match_name} -/" + formal_code
                    print(f"-> ✅ Grounded successfully. LLM chose: {best_match_name}")
                    return True
                else:
                # LLM 判断所有候选项都不合适
                    print(f"-> 🟡 Grounding failed. LLM determined no candidate was a good match.")
                    return False
            except Exception as e:
                print(f"-> ❗️ LLM reasoning step failed: {e}")
                return False
        else:
            # --- 这是 W/O RAG 消融实验的新逻辑 ---
            print(f"🚫 [w/o RAG Mode] Grounding '{node.name}' using only the LLM's internal knowledge...")
            
            prompt = f"""
You are an expert on the Lean 4 mathlib4 library, relying ONLY on your pre-trained knowledge.
A user wants to know if the mathematical concept "{node.name}" has a standard, canonical definition in the mathlib4 library.

**Your Task:**
1.  Based **only on your internal memory**, determine if a standard definition for "{node.name}" exists in mathlib4.
2.  If you confidently believe it exists, provide its full, formal name (e.g., `RingHom`, `Subgroup.IsMaximal`, `IsSimpleGroup`).
3.  If you believe it does not exist, or if you are not confident, you must state that it is not found.

**Your output MUST be a single, valid JSON object with the following keys:**
- "formal_name": The string of the full formal name if you believe one exists, otherwise `null`.
- "reasoning": A brief, one-sentence explanation for your decision. For example: "This is the standard class for this concept in my knowledge base." or "No standard definition for this concept was found in my training data."
"""

            try:
                response_json = await tools.llm_with_strict_format(
                    msgs=[{"role": "user", "content": prompt}],
                    config=self.config["llm"]["main_model"]
                )
                
                formal_name = response_json.get("formal_name")

                if formal_name:
                    # LLM 认为它知道这个定义
                    node.status = "grounded"
                    # 在消融模式下，我们没有真实的 formal_code，只有一个名字
                    # 这个名字可能是正确的、过时的(Mathlib 3)或完全是幻觉
                    node.formal_code = f"/- [w/o RAG] LLM believes the definition for '{node.name}' is: {formal_name} -/"
                    print(f"-> 🧠 Grounded via LLM knowledge. LLM recalled name: {formal_name}")
                    return True
                else:
                    print(f"-> 🟡 Grounding failed. LLM does not know a definition for '{node.name}'.")
                    return False
            except Exception as e:
                print(f"-> ❗️ LLM knowledge query failed: {e}")
                return False
            
        
    
    async def synthesize_definition(self, node: ConceptNode):
        """(Bottom-Up) 当所有依赖都准备好后，生成并验证新定义。"""
        print(f"🛠️ Synthesizing definition for '{node.name}'...")
        
        context_code = ""
        for dep_name in node.dependencies:
            dep_node = self.graph.nodes[dep_name]
            context_code += f"-- Prerequisite: {dep_name}\n{dep_node.formal_code}\n\n"
            
        initial_prompt = f"""
You are a meticulous expert in Lean 4 and `mathlib4`. Using the following verified Lean 4 definitions as context, write the formal Lean definition for "{node.name}".
Your output must be a single, well-formed Lean 4 code block. Do not add any explanation outside the code block.

**Context from Previous Steps:**
---
{context_code}
---

**Informal Definition of "{node.name}":**
{node.informal_description} 

**Your Task: Write the Lean 4 `def` or `class`:**
Caution: DO NOT use sorry to skip the value of the definition.
"""
        
        result = await tools.def_generate_and_verify_loop(
            initial_prompt=initial_prompt,
            config=self.config,
            max_retries=16,
            stats_tracker=self.stats_tracker,
            counter_key="definition_synthesis_calls"
        )
        
        if result["success"]:
            node.formal_code = result["code"]
            node.status = "synthesized"
            print(f"-> ✅ Synthesis successful for '{node.name}'.")
        else:
            node.formal_code = result["code"]
            node.error_message = result["error"]
            node.status = "failed"
            print(f"-> 🔥 Synthesis failed for '{node.name}' after multiple attempts.")


    async def run(self, target_concept: str, informal_context: str | None) -> str | None:
        """执行完整的 D-GoT 流程来形式化一个概念。"""
        if target_concept in self.synthesis_cache:
            print(f"✅ Found '{target_concept}' in cache. Reusing existing definition.")
            # 如果命中缓存，直接返回结果，跳过所有后续步骤
            return self.synthesis_cache[target_concept]
        self.graph.add_concept(target_concept, informal_description=informal_context)
        
        # 阶段一: 依赖解析 (Top-Down)
        print("\n--- STAGE 1: Dependency Resolution (Top-Down) ---")
        agenda = [target_concept]
        visited_for_expansion = set()

        while agenda:
            current_concept_name = agenda.pop(0)
            if current_concept_name in visited_for_expansion: continue
            
            node = self.graph.nodes[current_concept_name]
            node.status = "exploring"
            visited_for_expansion.add(current_concept_name)
            
            if not await self.ground_in_mathlib(node):
                await self.expand_dependencies(node)
                for dep in node.dependencies:
                    if dep not in visited_for_expansion:
                        agenda.append(dep)

        # 阶段二: 综合生成 (Bottom-Up)
        print("\n--- STAGE 2: Synthesis (Bottom-Up) ---")
        while (node := self.graph.get_ready_to_synthesize_node()) is not None:
            await self.synthesize_definition(node)
            
        final_node = self.graph.nodes[target_concept]
        
        if self.graph.is_complete(target_concept):
            print(f"\n🎉 Successfully formalized '{target_concept}'.")
            if final_node.formal_code:
                print(f"  -> Caching new definition for '{target_concept}'.")
                self.synthesis_cache[target_concept] = final_node.formal_code
            return final_node.formal_code
        else:
            print(f"\n🔥 Failed to formalize '{target_concept}'.")
            return None