# 🧮 MathLABS: Visual and Symbolic Mathematical Reasoning Dataset

MathLABS is a collaborative dataset project exploring **visual mathematical reasoning** and **symbolic problem solving** in modern LLMs and VLMs.  
The goal is to benchmark model reasoning on **small-data visual math problems** with structured, schema-aligned questions.

---

## Repository Structure
```
mathlabs/
│
├── dataset/ # Phase 1: All questions (baseline + validated)
│ ├── baseline.json #Intial pool
│ ├── unified.json #Combination of all extracted and generated
│ ├── verified.json #Verified and validated questions
│ └── images/
│
├── model_eval/ # Phase 2: Model experiments & evaluation
│ ├── prompts/ 
│ ├── results/
│ ├── metrics/
│ └── analysis/
│
├── docs/
│ ├── schema_description.md
│ ├── design_notes.md
│ └── roadmap.md
│
└── meta_data.json
```


---

## Workflow

### **Phase 1: Dataset**
All team members collaborate to create a robust baseline in ```baseline.json```, then split tasks for efficiency:

| Step | Description |
|------|-------------|
| **Baseline** | Initial question pool (~100 questions) across subfields (Algebra, Geometry, Probability, etc.)|
| **Extraction** | Extract diagrams, OCR text, and structured representations|
| **Generation** | LLM-assisted synthetic question creation|
| **Formatting** | Schema normalization, MSC2020 classification, difficulty tagging|
| **Validation** | Auto + manual verification of answers, reasoning, hints|

---

### **Phase 2: Model & Evaluation**
Use validated dataset to benchmark LLMs or other models:

| Step | Description | Output |
|------|-------------|--------|
| **Benchmarking** | Few-shot, zero-shot, or visual reasoning tasks | `model_eval/results/` |
| **Metric Analysis** | Compute accuracy, reasoning correctness, symbolic validation | `model_eval/metrics/` |
| **Visualization** | Graphs and summary analysis | `model_eval/analysis/` |

---

## Research Focus
- Reasoning with **small-data**  
- **Visual + symbolic** math problem understanding  
- **Few-shot and zero-shot** evaluation of LLMs  
- Dataset structured using **MSC2020 codes** for subfield/topic classification

---

## JSON Schema Example

```json
{
  "id": "ALG-001",
  "topic": "Linear Algebra",
  "msc2020_field": "15A18",
  "question": "Find the eigenvalues of A = [[1,2],[2,1]]",
  "answer": "[3, -1]",
  "difficulty": "medium",
  "source": "baseline",
  "validated": true
}
