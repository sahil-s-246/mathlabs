# Question Design Guide

## 1. Sources & MSC Classification

Each problem should include a source field to track its origin:

- Generated: Problem created by the team or AI. No external exam or textbook reference needed.
- Extracted: Problem taken from existing exams, textbooks, or other reliable sources. Citation required.
- MSC Codes: Use Mathematics Subject Classification codes to categorize the problem's subfield (e.g., 60 for probability, 11 for number theory). Helps in filtering and organizing the dataset.

Example source structure:

"source": {
  "type": "generated",  // or "extracted"
  "exam": "",           // optional for generated
  "textbook_citation": ""  // optional for generated
}

---

## 2. Fields Explanation

Each problem entry should contain the following fields:

Field | Purpose
------|--------
problem_id | Unique identifier for the problem
source | Tracks if the problem is generated or extracted
subfield | MSC classification code(s)
topic | High-level topic codes (e.g., probability, geometry)
gradelevel | Target education level (High-School, College-level, Infinity)
statement | Full text of the problem
diagram_data | Structured information for plotting/visuals
hints | Optional stepwise hints for solving
solution | Canonical answer, formula, or method
validation_status | verified or unverified
flags | Issues or errors such as vision_extraction_error, metadata_missing, solvability_issue

Example JSON snippet:

```json
{
  "problem_id": "prob-venn-001",
  "source": { "type": "generated" },
  "subfield": ["60"],
  "topic": ["probability", "venn_diagram"],
  "gradelevel": ["High-School", "College-level"],
  "statement": "In a class of 50 students, 30 study Math, 25 study Physics, and 10 study both Math and Physics. How many students study neither Math nor Physics?",
  "diagram_data": { ...},
  "hints": ["Use inclusion-exclusion formula", "Subtract total in union from total students"],
  "solution": "50 - (30 + 25 - 10) = 5",
  "validation_status": "unverified",
  "flags": []
}
```
---

## 3. Rubric

### Validity
- Must involve numbers, symbols, or quantities and require operations or reasoning.
- Must involve ≥2 reasoning steps.
- Include at least one math-related keyword (sum, difference, fraction, ratio, percent, mean, median, triangle, circle, cube, etc.).

Does NOT qualify if:
- No numbers or quantities present
- Only counting or recognition required
- Relies solely on factual recall

### Solvability
- Complete information provided
- Unique or clearly constrained solution
- Reasonable and logically consistent
- Computation feasible in reasonable time

### Visual Clarity
- Symbols and labels readable
- Diagram matches text description
- No distracting elements
- All critical visual elements present

### Bias Control
- Correct options evenly distributed
- No unintentional visual cues
- Avoid wording that reveals the answer
- Text and diagram do not leak answers

---

## 4. Validation & Error Flags

- Validation Status: verified or unverified
- Error Flags:
  - vision_extraction_error
  - metadata_missing
  - solvability_issue
- Evaluation Metrics: Check correctness, uniqueness, and clarity

---

## 5. Difficulty & Step-Based Evaluation

### Steps for Reasoning (S)
- Count reasoning steps required
- Thresholds:
  - Easy: 2 ≤ S ≤ 3
  - Medium: 3 < S ≤ 4
  - Hard: S > 4

### Weighted Factors
Factor | Description | Weight
-------|------------|-------
Step Complexity | Depth and number of reasoning steps | 0.5
Computational Effort | Calculation or symbolic manipulation | 0.2
Visual Interpretation | Complexity of diagram interpretation | 0.2
Optional Knowledge / Abstraction | Abstract thought or pattern recognition | 0.1

Example:
- 3 reasoning steps, moderate calculations, simple diagram, minimal abstraction
  - Step Complexity: 0.5 × 0.6 = 0.3
  - Computational Effort: 0.2 × 0.5 = 0.1
  - Visual Interpretation: 0.2 × 0.3 = 0.06
  - Optional Knowledge: 0.1 × 0.2 = 0.02
  - Total = 0.48 → Medium Difficulty

Notes:
- Include visual reasoning steps where interpreting diagrams is needed
- Use scores to filter, balance, or stratify the dataset

---

## 6. Summary

Provides a single reference for:
- Problem creation
- Field definitions
- Validation & error checking
- Bias control
- Difficulty grading

Ensures high-quality, consistent, and reproducible visual math problems for the dataset.
