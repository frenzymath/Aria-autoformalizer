SUBTASK_DECOMPOSITION_PROMPT = """\
Help me list the conditions and conclusions in this problem (using specific mathematical formulas), without solving it:

Here is an example:
[Problem]: The sequence {{a_n}} satisfies a₁ = 1, a₂ = 2, aₙ₊₂ = 2aₙ₊₁ − aₙ + 2. Let bₙ = aₙ₊₁ − aₙ. Prove that {{b_n}} is an arithmetic sequence.

[Conditions and Conclusions]:
Conditions:
1. a₁ = 1
2. a₂ = 2
3. ∀n ≥ 1, aₙ₊₂ = 2aₙ₊₁ − aₙ + 2
4. ∀n ≥ 1, bₙ = aₙ₊₁ − aₙ

Conclusion:
- {{b_n}} is an arithmetic sequence, i.e., ∃d ∈ ℝ, ∀n ≥ 1, bₙ₊₁ − bₙ = d.

Now, please help me extract the conditions and conclusions for this problem in the same way (using specific mathematical formulas), without solving it:
[Problem]: {problem}

[Conditions and Conclusions]:
"""

ONE_SHOT_EXAMPLE = """\
Let’s compare the mathematical conditions and conclusions with the Lean 4 formal statement one by one:

1. **q is a natural number greater than 1**:
- Math: q ∈ ℕ, q > 1.
- Lean: `(hq : 1 < q)`.
- Match: Perfectly match.

2. **n is a natural number greater than 1**:
- Math: n ∈ ℕ, n > 1.
- Lean: `(hn : 1 < n)`.
- Match: Perfectly match.

3. **Set M = {{0, 1, 2, ..., q − 1}}**:
- Math: M is explicitly defined as this set.
- Lean: `(M : Finset ℕ := Finset.range q)`.
- Match: Perfectly match.

4. **Set A definition**:
- Math: A = {{x | x = ∑ xᵢ qⁱ⁻¹, xᵢ ∈ M}}.
- Lean: `A : Set ℕ := {{x_vec : ℕ → ℕ | ∀ i ∈ M, ∃ x ∈ ℕ, x = ∑ i in Finset.range n, x_vec(i + 1) * q^i}}`.
- Match: Minor inconsistency.

5. **s, t ∈ A with specific expansions**:
- Math: s = ∑ aᵢ qⁱ⁻¹, t = ∑ bᵢ qⁱ⁻¹, with aᵢ, bᵢ ∈ M.
- Lean: `s = ∑ i in Finset.range n, a(i + 1) * q^i`, same for t and b.
- Match: Minor inconsistency.

6. **aₙ < bₙ**:
- Math: aₙ < bₙ.
- Lean: `(hab : a n < b n)`.
- Match: Perfectly match.

7. **Conclusion s < t**:
- Math: s < t.
- Lean: `s < t`.
- Match: Major inconsistency.

### Check for missing conditions / implicit conditions:
- No missing conditions / implicit conditions
- Match: Perfectly match.
"""

FEW_SHOTS_EXAMPLE = """\
### Minor inconsistency

Minor inconsistencies of a condition between a natural language statement and Lean statement may contain following circumstances:

1. Possible Redundency: Model may add redundant information to the Lean 4 statement that is not present in the natural language statement, in the sense that make the statement clearer but not strictly necessary.
   Example: P is a group with |P| = p^3
   - Math: |P| = p^3.
   - Lean: `(hP2 : Nat.card P = p ^ 3)` and `(hP1 : IsPGroup p P)`
   Here the Lean statement includes `IsPGroup p P` is redundant because the `hP2` already implies that `P` is a `p`-group.

2. Possible different interpretation: Model may interpret the natural language statement in a different way than intended, but they are mathematically equivalent. This circumstance may due to certain definition or structure that exists in Mathlib.
   Example: the identity is the only element of $G$ which commutes with all elements of $G$
   - Math: Let \(x\) be an element of \(G\). If \(x\) commutes with every element of \(G\), then \(x\) is the identity.
   - Lean: `Subgroup.centralizer ⊤ = (⊥ : Subgroup G)`
   Here, model take advantages of an existing definition in Lean 4, i.e. `centralizer` to rephrase the statement, and they are indeed logically equivalent.

### Major inconsistency

Major inconsistencies of a condition between a natural language statement and Lean statement may contain following circumstances:

1. Complete different meaning: Model may interpret the natural language statement in a irrelevant form, which is obviously not equivalent to the original statement.

2. Possible loosening: Model may interpret the natural language statement in a more general form than intended.
   Example: i and j are relatively prime integers
   - Math: i, j are relatively prime integers.
   - Lean: `{i j : ℤ} (h : IsRelPrime i j)`.
   Prime number require \(i\) and \(j\) to be natural numbers, instead of solely integers.
   
3. Possibly strict: Model may pose additional restriction on natural language statement or make some condition stronger when doing translation.
   Example: Let \(S\) be any ring.
   - Math: S is any ring.
   - Lean: S is a commutative ring (via `[CommRing S]`).
   Commutative ring is stricter than any ring, leading to different statement.
"""

ALL_EXAMPLES = ONE_SHOT_EXAMPLE + "\n\n" + FEW_SHOTS_EXAMPLE

NLI_JUDGE_PROMPT = """\
Here is a math question and a Lean 4 statement. Compare the conditions and conclusions in this code with the mathematical ones, matching them one by one to see if the formal statement is an appropriate translation of the mathematical condition by assigning one of three tags (Perfectly Match; Minor Inconsistency; Major Inconsistency). Then, audit for missing/implicit conditions. Judge with extremely strict standards—any minor inconsistency will be considered a mismatch. Special attention to triangle angle-side correspondence. If the question explicitly mentions "opposite angles/sides", this correspondence must be clearly stated and correct. 
**Stop immediately** after evaluating all pairs. Do **not** summarize or analyze further. 

Output Format:
{few_shots_example}

____________

Question:
{informal_statement}

Mathematical conditions and conclusions:
{math_conditions}

Lean 4 formal statement:
{formal_statement}

Here are the terms included in a Lean 4 formal statement:
{type_ref_lst}

Here are the official Mathlib entries for the terms in the Lean 4 statement. Each entry consists of its name, kind, type, value, informal_name, and informal_description. You must verify every condition and every conclusion by cross-checking them one by one against these Mathlib entries. These entries are the only authoritative reference; you are strictly forbidden to rely on assumptions or background knowledge outside of them. 
Any discrepancy between the Lean statement and the Mathlib entries must be marked as an inconsistency.
{ls_results}

Output:
"""


NLI_JUDGE_PROMPT_NO_JIXIA = """\
Here is a math question and a Lean 4 statement. Compare the conditions and conclusions in this code with the mathematical ones, matching them one by one to see if the formal statement is an appropriate translation of the mathematical condition by assigning one of three tags (Perfectly Match; Minor Inconsistency; Major Inconsistency). Then, audit for missing/implicit conditions. Judge with extremely strict standards—any minor inconsistency will be considered a mismatch. Special attention to triangle angle-side correspondence. If the question explicitly mentions "opposite angles/sides", this correspondence must be clearly stated and correct. 
**Stop immediately** after evaluating all pairs. Do **not** summarize or analyze further. 

Output Format:
{few_shots_example}

____________

Question:
{informal_statement}

Mathematical conditions and conclusions:
{math_conditions}

Lean 4 formal statement:
{formal_statement}

Output:
"""