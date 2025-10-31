```
[
"""
You are a discrete professor. For every question below, return **only** a JSON array with one object per question. 
Each object must contain:
  - final_answer: the correct letter (A/B/C/D)
  - difficulty: easy / medium / hard
  - shuffle: true / false
  - issues: [] (or list of strings)

Return **nothing else** – no markdown, no extra text.

QUESTION 0 (problem_id: {q['problem_id']})
{q['statement']}

{choices}

Claimed answer: {q['answer']['correct_ids'][0]}
Claimed difficulty: {q.get('difficulty', 'unknown')}
---
QUESTION 1 (problem_id: {q['problem_id']})
{q['statement']}

{choices}

Claimed answer: {q['answer']['correct_ids'][0]}
Claimed difficulty: {q.get('difficulty', 'unknown')}
---

Output JSON array now:
""",
]
```
