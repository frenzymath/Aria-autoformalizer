from typing import List
import re
from openai import OpenAI
from config import *

# 计算模糊积分
def compute_fuzzy_score(ratings: List[str]) -> float:
    """
    ratings: 规范化为 'A' | 'B' | 'C' 的列表
    A=Perfectly Match, B=Minor Inconsistency, C=Major Inconsistency
    公式:
        μ(M) =
        1                                      , if all are A
        max{ |M_A|/n * (1 - 0.2*|M_B| ), 0 }   , if |M_B| ≥ 2
        |M_A|/n * (1 - 0.1*|M_B| )             , if |M_B| = 1
        0                                      , if ∃ C
    """
    n = len(ratings)
    if n == 0:
        return 0.0

    count_A = sum(r == 'A' for r in ratings)
    count_B = sum(r == 'B' for r in ratings)
    count_C = sum(r == 'C' for r in ratings)

    if count_C > 0:
        return 0.0

    if count_A == n:
        return 1.0

    if count_B == 1:
        return (count_A / n) * (1.0 - 0.1 * count_B)

    if count_B >= 2:
        return max((count_A / n) * (1.0 - 0.2 * count_B), 0.0)

    return count_A / n if n > 0 else 0.0


# 抓取评分
_MATCH_LINE_RE = re.compile(
    r"(?im)^\s*[-*]?\s*Match\s*:\s*(?:\\box\{)?\s*"
    r"(Perfect(?:ly)?\s*match|Minor\s*inconsistency|Major\s*inconsistency|[ABC])"
)

_FALLBACK_LABEL_RE = re.compile(
    r"(?i)\b(Perfect(?:ly)?\s*match|Minor\s*inconsistency|Major\s*inconsistency|[ABC])\b"
)

def _normalize_to_abc(s: str) -> str | None:
    t = s.strip().lower()
    if t in ("a", "b", "c"):
        return t.upper()
    if t.startswith("perfect"):  # Perfect / Perfectly match
        return "A"
    if t.startswith("minor"):    # Minor inconsistency
        return "B"
    if t.startswith("major"):    # Major inconsistency
        return "C"
    return None

def _extract_ratings_from_output(output: str) -> List[str]:
    hits = _MATCH_LINE_RE.findall(output)
    if not hits:
        hits = _FALLBACK_LABEL_RE.findall(output)

    ratings: List[str] = []
    for h in hits:
        abc = _normalize_to_abc(h)
        if abc is not None:
            ratings.append(abc)
    return ratings

def call_llm_gemini(prompt: str, max_tokens: int = 2048) -> str:
    client = OpenAI(
        base_url=GEMINI_API_BASE,
        api_key=GEMINI_API_KEY,
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=GEMINI_MODEL_NAME,
    )
    
    return chat_completion.choices[0].message.content

if __name__ == '__main__':
    with open('/volume/math/users/ytwang/rhxie/autoformalizers/Lean Scorer/result_search/FATE-X/agent_fatex_pass@16_verified_100_r_0912_full_output.txt', 'r') as f:
        full_text = f.read()
    
    pattern = re.compile(r"LLM Full Output:\s*(.*?)\s*={5,}", re.S)
    m = pattern.findall(full_text)
    
    for i in range(len(m)):
        text = m[i]
        res = _extract_ratings_from_output(text)
        print(text)
        print("\n==================================\n")
        print(res)
        print("\n")

    