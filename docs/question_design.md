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
schema_version | Version of the schema
problem_id | Unique identifier for the problem
source | Tracks if the problem is generated or extracted
subfield | MSC classification code(s)
topic | High-level topic codes (e.g., probability, geometry)
gradelevel | Target education level (High-School, College-level, Infinity)
statement | Full text of the problem
diagram_data | Structured information for plotting/visuals
answer | Answer to the question, including the rationale for distractors
randomization | Randomization to the parameters of the sampling
hints | Optional stepwise hints for solving
difficulty | Difficulty of the question
bloom_taxonomy | Bloom taxonomy category (e.g. 'Analyze', 'Apply', etc.)
validation_status | verified or unverified
flags | Issues or errors such as vision_extraction_error, metadata_missing, solvability_issue

Example JSON snippet:

```json
{
  "schema_version": "mcq-1.0",
  "problem_id": "11-006",
  "question_type": "multiple_choice", 
  "source": {
    "type": "extract",
    "book_title": "Elementary Number Theory",
    "authors": ["David M. Burton"],
    "edition": 7,
    "chapter": 1,
    "page": 302
  },
  "subfield": ["11"],
  "topic": [
	  "number_theory",
    "fibonacci_numbers",
    "binomial_coefficients",
    "combinatorics",
    "algebraic_identities"
    ],
  "gradelevel": ["College-level"],
  "statement": "Lucas showed in 1876 that each Fibonacci number $F_n$ can be written as a sum of binomial coefficients. Which of the following correctly expresses $F_n$ in terms of binomial coefficients?",
  "diagram_data": {
    "type": "formula|image|table",
    "image_path": "images/11-006.png"
  },

  "choices": [
    { "id": "A", 
	    "text": "$F_n = \\sum_{k=0}^{\\lfloor (n-1)/2 \\rfloor} \\binom{n-1-k}{k}$"
	  },
    { "id": "B", 
	    "text": "$F_n = \\sum_{k=0}^{n} \\binom{n}{k}$" 
	  },
    { "id": "C", 
	    "text": "$F_n = \\sum_{k=0}^{\\lfloor n/2 \\rfloor} \\binom{n-k}{k}$" 
	  },
    { "id": "D", 
	    "text": "$F_n = \\sum_{k=1}^{n-1} \\binom{n}{2k}$" 
	  }
  ],

  "answer": {
    "correct_ids": ["A"],                  
    "explanation": "Define $a_n = \\sum_{k=0}^{\\lfloor (n-1)/2 \\rfloor} \\binom{n-1-k}{k}$. Using Pascal’s identity $\\binom{m}{r}=\\binom{m-1}{r}+\\binom{m-1}{r-1}$, one can show that $a_{n+1}=a_n+a_{n-1}$ with $a_1=a_2=1$, implying $a_n$ satisfies the Fibonacci recurrence. Hence $F_n = a_n = \\sum_{k=0}^{\\lfloor (n-1)/2 \\rfloor} \\binom{n-1-k}{k}$, known as Lucas’s binomial formula.",
    "distractor_rationales": {             // optional: discussion why the distractors are wrong
      "B": "This sum equals $2^n$, not the $n$-th Fibonacci number.",
      "C": "This looks close but the upper limit and indices differ; it defines $F_{n+1}$, not $F_n$.",
      "D": "Even-indexed binomial terms do not follow the Fibonacci recurrence; this expression relates to central binomial coefficients, not Fibonacci numbers."
    },
  },

  "evaluation": {
    "scoring": { "type": "all_or_nothing", "points": 1 },
    "allow_partial_credit": false          // may be true for MCQs allowing more than one answers
  },

  "randomization": {
    "shuffle_choices": true,               // whether or not some choicees should be shuffled
    "lock_ids": [],                        // questions that require to be locked in place
    "group_shuffle": []                    // question ids that should be shuffled together (that they are similar)
  "hints": 
  [
		"Try expressing $F_n$ recursively as $F_{n+1}=F_n+F_{n-1}$.",
    "Define $a_n=\\sum_{k=0}^{\\lfloor (n-1)/2\\rfloor} \\binom{n-1-k}{k}$ and verify it satisfies the same recurrence.",
    "Use Pascal's identity to expand $\\binom{n-k}{k}$ and split into two sums." 
   ],
  "difficulty": "medium",
  "bloom_taxonomy": ['Comprehend', 'Analyze'],
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
