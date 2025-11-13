import json
import re
import time
from typing import Dict, List, Union, Any, Optional
from openai import BadRequestError
from loguru import logger
import traceback
import sys
import os
import sys
from pathlib import Path
import requests
import Levenshtein
import hashlib
import xlsxwriter
from src.PocketFlow import Flow
import aiohttp
import asyncio
import yaml
from openai import (
    AsyncOpenAI,
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    APIConnectionError,
    APITimeoutError
)
# 导入 OpenAI API 的返回类型，用于类型注解
from openai.types.chat import ChatCompletion

from .pretty_error import VerifyResult, pp_verify_result

DEF_REFINEMENT_PROMPT_TEMPLATE = """
You are a Lean 4 expert. The following code you previously generated has a compilation error.
Your task is to analyze the error message and provide a corrected version of the code.
You MUST follow this two-step process:

**Step 1: Analysis and Correction Plan**
First, provide a brief analysis of the problem in the following format:
1.  **Error Analysis:** [Summarize the main error message in one sentence]
2.  **Root Cause:** [Explain the underlying reason for the error, e.g., missing typeclass instance, type mismatch between a term and its expected type, incorrect syntax, etc.]
3.  **Correction Plan:** [Describe the specific code change you will make to fix the issue, e.g., "Change the typeclass constraint from [Semiring R] to [Ring R]", "Explicitly access the underlying ideal using .toIdeal", etc.]

**Step 2: Corrected Lean 4 Code**
Then, provide the complete, corrected code in a single Lean code block.
Do not change the original theorem statement, only fix the proof or definition.
**Caution:** 
You are not sure about the explicit header, so DO NOT generate explicit header like 'import Mathlib.RingTheory.Noetherian', USE 'import Mathlib'. **Crucially, you must NOT write the proof.** Your only goal is to state the theorem correctly.

**Failed Code:**
```lean
{code}
```

**Error Message from Lean Compiler:**
{error}

**Your Task:**
Provide the complete, corrected Lean 4 code in a single code block, without any extra explanation. USE 'import Mathlib' as a header!
"""
STAT_REFINEMENT_PROMPT_TEMPLATE = """
You are a Lean 4 expert. The following code you previously generated has a compilation error.
Your task is to analyze the error message and provide a corrected version of the code.
Do not change the original theorem statement and the definitions, only fix the code.
**Caution:** 
You are not sure about the explicit header, so DO NOT generate explicit header like 'import Mathlib.RingTheory.Noetherian', use 'import Mathlib'. **Crucially, you must NOT write the proof.** Your only goal is to state the theorem correctly. The proof block must be replaced with the `sorry` keyword.

**Failed Code:**
```lean
{code}
```

**Error Message from Lean Compiler:**
{error}

**Your Task:**
Provide the complete, corrected Lean 4 code in a single code block, without any extra explanation. USE 'import Mathlib' as a header!
"""
async def llm(msgs: List, config: Dict, max_retries: int = 5):
    
    for attempt in range(max_retries):
        try:
            print(f"  [LLM] Attempt {attempt + 1}/{max_retries} to connect to API server...")
            client = AsyncOpenAI(
                base_url=config["base_url"],
                api_key=config["api_key"],
                timeout=600.0,
            )
            
            response = await client.chat.completions.create(
                model=config["model"],
                messages=msgs,
                stream=False,
                temperature=config.get("temperature", 1),
                max_completion_tokens=config.get("max_completion_tokens", 20000) # 修正了 OpenAI v1.x 的参数名
            )
            print(f"  [LLM] API call successful on attempt {attempt + 1}.")
            return response # <--- 成功时直接返回结果，跳出循环

        # --- 可重试的错误 ---
        except (APIConnectionError, APITimeoutError, RateLimitError) as e:
            wait_time = 2 ** attempt
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            if isinstance(e, APITimeoutError):
                print("!!!!!!!!!!! [WARNING] TIMEOUT ERROR !!!!!!!!!!!")
                print(f"!!!!!!!!!!! API request timed out. Retrying in {wait_time} seconds...")
            elif isinstance(e, RateLimitError):
                print("!!!!!!!!!!! [WARNING] RATE LIMIT ERROR !!!!!!!!!!!")
                print(f"!!!!!!!!!!! Rate limit reached. Retrying in {wait_time} seconds...")
            else:
                print("!!!!!!!!!!! [WARNING] CONNECTION ERROR !!!!!!!!!!!")
                print(f"!!!!!!!!!!! Could not connect to API server. Retrying in {wait_time} seconds...")
            print(f"!!!!!!!!!!! Error details: {e}")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            
            # 如果不是最后一次尝试，就等待后重试
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
            else:
                print("!!!!!!!!!!! [FATAL] Max retries reached. Giving up. !!!!!!!!!!!")

        # --- 致命的、不可重试的错误 ---
        except (AuthenticationError, NotFoundError) as e:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!!!!!!!!!! [FATAL] UNRECOVERABLE API ERROR !!!!!!!!!!!")
            if isinstance(e, AuthenticationError):
                print("!!!!!!!!!!! Authentication failed. Check your API Key. !!!!!!!!!!!")
            else: # NotFoundError
                print(f"!!!!!!!!!!! Model '{config.get('model')}' not found. Check model name. !!!!!!!!!!!")
            print(f"!!!!!!!!!!! Error details: {e}")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # 直接抛出异常，因为重试没有意义
            raise e

        # --- 其他 API 错误 ---
        except APIError as e:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!!!!!!!!!! [ERROR] GENERAL API ERROR !!!!!!!!!!!")
            print(f"!!!!!!!!!!! API server returned an error. Status code: {e.status_code}")
            print(f"!!!!!!!!!!! Error details: {e}")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # 这种错误有时也可以重试，但我们这里选择放弃
            break

        # --- 未知错误 ---
        except Exception as e:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!!!!!!!!!! [CRITICAL] UNEXPECTED ERROR !!!!!!!!!!!")
            traceback.print_exc()
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # 未知错误通常不应该重试，直接中断
            break

    # 如果循环结束了还没有成功返回，说明所有重试都失败了
    return None

async def collect_response_frm_stream(stream, verbose: bool = False):
    think = ""
    result = ""
    try:
        async for chunk_obj in stream:
            if chunk_obj.choices and len(chunk_obj.choices) > 0:
                delta = chunk_obj.choices[0].delta
                if delta:
                    if (
                        hasattr(delta, "reasoning_content")
                        and delta.reasoning_content is not None
                    ):
                        if verbose:
                            print(delta.reasoning_content, end="")
                        think += delta.reasoning_content
                    elif (
                        hasattr(delta, "reasoning")
                        and delta.reasoning is not None
                    ):
                        if verbose:
                            print(delta.reasoning, end="")
                        think += delta.reasoning

                    elif hasattr(delta, "content") and delta.content is not None:
                        result += delta.content or ""
                        if verbose:
                            print(delta.content, end="")

    except Exception as e:
        error_msg = f"{str(traceback.format_exc())}\n\n{str(sys.exc_info()[2])}"
        logger.error(f"Error during streaming: {e} \n{error_msg}")

    # some reasoning model only contain "</think>"
    if len(think) == 0 and "</think>" in result:
        think = result.split("</think>")[0].split("<think>")[1]
        result = result.split("</think>")[1]

    return {"think": think, "result": result}


async def llm_with_strict_format(
    msgs: List, config: Dict, max_try_num: int = 1, block_type: str = "json"
):
    client = AsyncOpenAI(
        base_url=config.get("base_url"),
        api_key=config.get("api_key"),
        timeout=600
    )

    while max_try_num > 0:
        stream = await client.chat.completions.create(
            model=config.get("model"),
            messages=msgs,
            stream=True,
            temperature=config.get("temperature", 1),
            max_completion_tokens=config.get("max_completion_tokens",8192),
        )
        response = await collect_response_frm_stream(stream)
        think = response["think"]
        result = response["result"]

        extract_content = extract_code_block(result, block_type)
        if extract_content is not None:
            return extract_content
        else:
            return json.loads(result)

    return ""


def safe_json_loads(s: str) -> dict:
    """
    Try to parse JSON string as dictionary.
    If encountering invalid escape sequences (like \*), automatically fix them.
    """
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        if "Invalid \\escape" in str(e):
            # 自动修复单个反斜杠：只转义未合法转义的反斜杠
            s_fixed = re.sub(r'(?<!\\)\\(?![\\/"bfnrtu])', r"\\\\", s)
            try:
                return json.loads(s_fixed)
            except Exception as e2:
                raise ValueError(f"JSON fix failed: {e2}")
        else:
            raise ValueError(f"JSON parsing failed: {e}")


def extract_code_block(
    response: str, block_type: str = "json", return_org_content: bool = False
) -> Union[str, dict, None]:
    """
    Extracts content from a markdown block in a string.

    Args:
        response (str): The string containing the markdown block.
        block_type (str, optional): The type of the markdown block (e.g., 'json', 'markdown'). Defaults to 'json'.
        return_org_content (bool, optional): Whether to return the original content if no block is found. Defaults to False.

    Returns:
        str or dict or None: The extracted content, or None if no block is found and return_org_content is False.
    """
    try:
        extract_content = re.findall(
            r"```" + block_type + r"([\s\S]*?)```", response, re.DOTALL
        )
        if len(extract_content) > 0:
            if block_type == "json":
                return safe_json_loads(extract_content[0])
            else:
                return extract_content[-1]
        else:
            if return_org_content:
                return response
            else:
                return None
    except Exception as e:
        print(e)
        if return_org_content:
            return response
        else:
            return None


def lean_check(code: str) -> Dict:
    url = ""
    try:
        response = requests.post(url, json={"code": code, "timeout": 1600})
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        return {"error": str(e)}


async def async_lean_check(session, code: str) -> VerifyResult:
    url = "http://repl-server-1.t-skyinfer-ytwang.svc.cluster.local/verify"
    try:
        async with session.post(url, json={"code": code, "timeout": 60}) as response:
            result_dict = await response.json()
            return VerifyResult.model_validate(result_dict)
    except Exception as e:
        return VerifyResult.from_system_error(code, 60, str(e))
    
    

async def def_generate_and_verify_loop(
    initial_prompt: str,
    config: Dict,
    max_retries: int = 3,
    stats_tracker: Optional[Dict] = None,
    counter_key: str = "default_def_calls"
) -> Dict:
    """
    管理一个完整的“生成-验证-修正”循环。
    """
    conversation_history: List[Dict[str, str]] = [{"role": "user", "content": initial_prompt}]
    
    current_code = ""
    current_prompt = initial_prompt

    async with aiohttp.ClientSession() as session:
        for i in range(max_retries):
            print(f"  Attempt {i + 1}/{max_retries}...")
            if stats_tracker is not None:
                stats_tracker[counter_key] = stats_tracker.get(counter_key, 0) + 1
            # --- 步骤 1: 生成代码 ---
            response = await llm(conversation_history, config["llm"]["main_model"])
            
            llm_result_content = ""
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                llm_result_content = response.choices[0].message.content
            
            conversation_history.append({"role": "assistant", "content": llm_result_content})

            if not llm_result_content:
                print("LLM failed to generate")
            current_code = extract_code_block(llm_result_content, "lean4", return_org_content=True)
            if current_code is None:
                current_code = extract_code_block(llm_result_content, "lean", return_org_content=True)
            print(current_code)
            if not current_code:
                error_msg = "LLM failed to generate a valid code block."
                print(f"  ❌ {error_msg}")
                if i == max_retries - 1: return {"success": False, "code": "", "error": error_msg}
                current_prompt = initial_prompt + "Please provide the complete code in a ```lean ... ``` block."
                continue

            # --- 步骤 2: 验证代码 ---=
            verification_result = await async_lean_check(session, current_code)

            # --- 步骤 3: 检查结果 ---
            if verification_result.pass_:
                print("  ✅ Verification PASSED!")
                return {"success": True, "code": current_code, "error": None}
            else:
                print(verification_result)
                sorted_messages = verification_result.sorted_messages
                error_list = sorted_messages.errors

                if error_list:
                    error_msg = pp_verify_result(verification_result)
                else:
                    error_msg = "No specific error message found."
                print(f"  ❌ Verification FAILED. Error: {str(error_msg)}...")
                if i == max_retries - 1:
                    return {"success": False, "code": current_code, "error": str(error_msg)}
            
                # --- 步骤 4: 准备下一次修正 ---
                print("  Preparing for refinement...")
                refinement_prompt = DEF_REFINEMENT_PROMPT_TEMPLATE.format(
                    code=current_code,
                    error=error_msg
                )
                conversation_history.append({"role": "user", "content": refinement_prompt})
                print(conversation_history)

    return {"success": False, "code": "", "error": "Max retries loop finished unexpectedly."}

async def stat_generate_and_verify_loop(
    initial_prompt: str,
    config: Dict,
    max_retries: int = 3,
    stats_tracker: Optional[Dict] = None,
    counter_key: str = "default_theorem_calls"
) -> Dict:
    """
    管理一个完整的“生成-验证-修正”循环。
    """
    conversation_history: List[Dict[str, str]] = [{"role": "user", "content": initial_prompt}]
    
    current_code = ""
    current_prompt = initial_prompt

    async with aiohttp.ClientSession() as session:
        for i in range(max_retries):
            print(f"  Attempt {i + 1}/{max_retries}...")
            if stats_tracker is not None:
                stats_tracker[counter_key] = stats_tracker.get(counter_key, 0) + 1
            # --- 步骤 1: 生成代码 ---
            response = await llm(conversation_history, config["llm"]["main_model"])
            
            llm_result_content = ""
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                llm_result_content = response.choices[0].message.content
            
            conversation_history.append({"role": "assistant", "content": llm_result_content})

            if not llm_result_content:
                print("LLM failed to generate")
            current_code = extract_code_block(llm_result_content, "lean4", return_org_content=True)
            if current_code is None:
                current_code = extract_code_block(llm_result_content, "lean", return_org_content=True)
            print(current_code)
            if not current_code:
                error_msg = "LLM failed to generate a valid code block."
                print(f"  ❌ {error_msg}")
                if i == max_retries - 1: return {"success": False, "code": "", "error": error_msg}
                current_prompt = initial_prompt + "Please provide the complete code in a ```lean ... ``` block."
                continue

            # --- 步骤 2: 验证代码 ---=
            verification_result = await async_lean_check(session, current_code)

            # --- 步骤 3: 检查结果 ---
            if verification_result.pass_:
                print("  ✅ Verification PASSED!")
                return {"success": True, "code": current_code, "error": None}
            else:
                print(verification_result)
                sorted_messages = verification_result.sorted_messages
                error_list = sorted_messages.errors

                if error_list:
                    error_msg = pp_verify_result(verification_result)
                else:
                    error_msg = "No specific error message found."
                print(f"  ❌ Verification FAILED. Error: {str(error_msg)}...")
                if i == max_retries - 1:
                    return {"success": False, "code": current_code, "error": str(error_msg)}
            
                # --- 步骤 4: 准备下一次修正 ---
                print("  Preparing for refinement...")
                refinement_prompt = STAT_REFINEMENT_PROMPT_TEMPLATE.format(
                    code=current_code,
                    error=error_msg
                )
                conversation_history.append({"role": "user", "content": refinement_prompt})
                print(conversation_history)

    return {"success": False, "code": "", "error": "Max retries loop finished unexpectedly."}

def format_formal_statement(result: Dict[str, Any]) -> str:
    """
    将 LeanSearch 返回的 result JSON 对象组合成一个形式化的 Lean 语句字符串。
    """
    kind = result.get("kind", "def")
    # 将名称列表用点连接起来，例如 ["Mathlib", "Order", "Filter", "Basic"] -> "Mathlib.Order.Filter.Basic"
    name = ".".join(result.get("name", []))
    signature = result.get("signature", "")
    type_str = result.get("type", "sorry")
    value = result.get("value")

    # 清理 signature 和 type 中可能存在的多余空格
    signature = " ".join(signature.strip().split())
    type_str = " ".join(type_str.strip().split())

    # 根据 kind 构建语句
    if kind in ["structure", "class", "inductive"]:
        # 这些类型通常没有 `:= value`
        formal_statement = f"{kind} {name}{signature} : {type_str}"
    else:
        # 其他类型如 def, theorem, lemma, instance 等
        body = ""
        if value:
            body = f":= {value}"
        else:
            # 如果没有提供 value，使用 sorry 作为占位符
            body = ":= sorry"
        formal_statement = f"{kind} {name}{signature} : {type_str} {body}"
        
    return formal_statement
