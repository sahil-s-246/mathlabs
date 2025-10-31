#!/usr/bin/env python3
"""
MathLabs Evaluator – FINAL WORKING VERSION
- Validation prompt copied from test_eval.py (works!)
- No HTTP 400, no ZeroDivisionError
- mode="test"/"db", sampler="random"/"sequential"
"""

import os
import json
import random
import base64
import time
import requests
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------- #
# CONFIG
# --------------------------------------------------------------------------- #
API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    raise RuntimeError("Set OPENROUTER_API_KEY in .env")

# File paths (test mode)
JSON_MCQ_FILE = "../dataset/baseline_lucas.json"
JSON_EVAL_FILE = "evaluations.json"

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "mathlabs"
MCQ_COLLECTION = "mcqs"
EVAL_COLLECTION = "evaluations"

# Shared
IMAGE_DIR = "/Users/sahilsrinivas/Developer/mathlabs/dataset/images"
MASTER_MODEL = "anthropic/claude-opus-4"
STUDENT_MODELS = [
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-4",
]
BATCH_SIZE = 2  # Safe for validation
SHUFFLE_CHOICES = True


# --------------------------------------------------------------------------- #
# EVALUATOR CLASS
# --------------------------------------------------------------------------- #
class MathLabsEvaluator:
    def __init__(self, mode: str = "test", sampler: str = "random"):
        self.mode = mode.lower()
        self.sampler = sampler.lower()

        if self.mode not in ["test", "db"]:
            raise ValueError("mode must be 'test' or 'db'")
        if self.sampler not in ["random", "sequential"]:
            raise ValueError("sampler must be 'random' or 'sequential'")

        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

        if self.mode == "db":
            self.client = MongoClient(MONGO_URI)
            self.db = self.client[DB_NAME]
            self.mcqs = self.db[MCQ_COLLECTION]
            self.evals = self.db[EVAL_COLLECTION]
            print(f"Mode: MongoDB | Sampler: {self.sampler}")
        else:
            print(f"Mode: JSON (test) | Sampler: {self.sampler}")

    # ------------------------------------------------------------------- #
    # LOAD MCQs
    # ------------------------------------------------------------------- #
    def load_mcqs(self, sample_size: int) -> List[Dict]:
        if self.mode == "db":
            if self.sampler == "random":
                pipeline = [{"$sample": {"size": sample_size}}]
                selected = list(self.mcqs.aggregate(pipeline))
            else:
                selected = list(self.mcqs.find({}).limit(sample_size).sort("problem_id", 1))
        else:
            if not os.path.exists(JSON_MCQ_FILE):
                raise FileNotFoundError(f"{JSON_MCQ_FILE} not found")
            with open(JSON_MCQ_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            all_mcqs = []
            if isinstance(data, list):
                for q in data:
                    if "problem_id" not in q: continue
                    all_mcqs.append(q.copy())
            elif isinstance(data, dict):
                for pid, q in data.items():
                    if pid == "schema_version": continue
                    q = q.copy()
                    q["problem_id"] = pid
                    all_mcqs.append(q)
            else:
                raise ValueError("mcqs.json must be list or dict")

            if self.sampler == "random":
                selected = random.sample(all_mcqs, min(sample_size, len(all_mcqs)))
            else:
                selected = all_mcqs[:sample_size]

        print(f"Selected {len(selected)} questions")
        return selected

    # ------------------------------------------------------------------- #
    # SAVE EVALUATION
    # ------------------------------------------------------------------- #
    def save_evaluation(self, eval_doc: Dict):
        if self.mode == "db":
            self.evals.update_one(
                {"test_run_id": eval_doc["test_run_id"]},
                {"$set": eval_doc},
                upsert=True
            )
            print(f"Saved to MongoDB: {eval_doc['test_run_id']}")
        else:
            if os.path.exists(JSON_EVAL_FILE):
                with open(JSON_EVAL_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            else:
                existing = []
            existing.append(eval_doc)
            with open(JSON_EVAL_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            print(f"Saved to {JSON_EVAL_FILE}")

    # ------------------------------------------------------------------- #
    # API CALL (FIXED)
    # ------------------------------------------------------------------- #
    def call_model(self, model: str, messages: List[Dict], image_path: Optional[str] = None) -> Dict:
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

        # Create a copy of the messages to avoid modifying the original
        final_messages = [msg.copy() for msg in messages]

        if image_path:
            # This logic is for adding an image to the *first* message
            full_path = os.path.join(IMAGE_DIR, os.path.basename(image_path))
            try:
                with open(full_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()

                # Assume the text prompt is in the first message's content
                text_prompt = final_messages[0]['content']

                # Re-format the content of the first message to be multimodal
                final_messages[0]['content'] = [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            except Exception as e:
                print(f"Image error: {e}")
                # If image fails, it will proceed as a text-only call

        # *** THIS IS THE FIX ***
        # The payload's "messages" key should be the list itself,
        # not nested inside another message structure.
        payload = {"model": model, "messages": final_messages}

        start = time.time()
        try:
            r = requests.post(self.base_url, headers=headers, json=payload, timeout=90)
            ms = int((time.time() - start) * 1000)
            if r.status_code != 200:
                error_msg = f"HTTP {r.status_code}: {r.text[:200]}"
                print(f"  API Error: {error_msg}")  # Added for better debugging
                return {"error": True, "content": error_msg, "time_ms": ms}
            return {"error": False, "content": r.json()["choices"][0]["message"]["content"], "time_ms": ms}
        except Exception as e:
            return {"error": True, "content": f"Exception: {e}", "time_ms": int((time.time() - start) * 1000)}
    # ------------------------------------------------------------------- #
    # VALIDATION PROMPT – COPIED FROM test_eval.py (WORKS!)
    # ------------------------------------------------------------------- #
    def build_validation_prompt(self, batch: List[Dict]) -> str:
        parts = [
            "You are a discrete professor. For every question below, return **only** a JSON array with one object per question. "
            "Each object must contain:\n"
            "  - final_answer: the correct letter (A/B/C/D)\n"
            "  - difficulty: easy / medium / hard\n"
            "  - shuffle: true / false\n"
            "  - issues: [] (or list of strings)\n\n"
            "Return **nothing else** – no markdown, no extra text.\n\n"
        ]

        for i, q in enumerate(batch):
            choices = "\n".join(f"{c['id']}) {c['text']}" for c in q["choices"])
            parts.append(
                f"QUESTION {i} (problem_id: {q['problem_id']})\n"
                f"{q['statement']}\n\n"
                f"{choices}\n\n"
                f"Claimed answer: {q['answer']['correct_ids'][0]}\n"
                f"Claimed difficulty: {q.get('difficulty', 'unknown')}\n"
                f"---\n"
            )

        prompt = "".join(parts).rstrip("---\n") + "\n\nOutput JSON array now:"

        return prompt

    # ------------------------------------------------------------------- #
    # PARSE VALIDATION – ROBUST
    # ------------------------------------------------------------------- #
    def parse_validation(self, text: str) -> List[Dict]:
        m = re.search(r"\[\s*{.*?}\s*(?:,\s*{.*?}\s*)*\]", text, re.DOTALL)
        if not m:
            print("No JSON array found in validation response")
            return []
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}\nRaw chunk:\n{m.group(0)[:500]}")
            return []

    # ------------------------------------------------------------------- #
    # APPLY VALIDATION
    # ------------------------------------------------------------------- #
    def apply_validation(self, mcq: Dict, val: Dict) -> Dict:
        orig_ans = mcq["answer"]["correct_ids"][0]
        orig_diff = mcq.get("difficulty", "unknown")

        if val["final_answer"] != orig_ans:
            mcq["answer"]["correct_ids"] = [val["final_answer"]]
        if val["difficulty"] != orig_diff:
            mcq["difficulty"] = val["difficulty"]

        if SHUFFLE_CHOICES and val.get("shuffle", False):
            random.shuffle(mcq["choices"])
            old_correct = val["final_answer"]
            for c in mcq["choices"]:
                if c["text"] == next((x["text"] for x in mcq["choices"] if x["id"] == old_correct), None):
                    mcq["answer"]["correct_ids"] = [c["id"]]
                    break

        mcq["validation"] = {
            "validated_by": MASTER_MODEL,
            "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            "original_answer": orig_ans,
            "final_answer": val["final_answer"],
            "original_difficulty": orig_diff,
            "final_difficulty": val["difficulty"],
            "shuffle_applied": SHUFFLE_CHOICES and val.get("shuffle", False),
            "issues": val.get("issues", [])
        }
        return mcq

    # ------------------------------------------------------------------- #
    # STUDENT EVAL
    # ------------------------------------------------------------------- #
    def build_student_prompt(self, mcq: Dict) -> str:
        choices = "\n".join(f"{c['id']}) {c['text']}" for c in mcq["choices"])
        return f"Answer this MCQ.\n\n{mcq['statement']}\n\n{choices}\n\nANSWER: <letter>\nREASONING: <2-3 sentences>"

    def extract_answer(self, text: str) -> Optional[str]:
        m = re.search(r"ANSWER:\s*([A-D])", text, re.I)
        if m: return m.group(1).upper()
        for l in "ABCD":
            if re.search(rf"\b{l}\b", text[:120]): return l
        return None

    def extract_reasoning(self, text: str) -> str:
        m = re.search(r"REASONING:\s*(.+)", text, re.I | re.S)
        return (m.group(1).strip() if m else text)[:500]

    def evaluate_question(self, mcq: Dict) -> Dict:
        img = mcq.get("diagram_data", {}).get("image_path")
        prompt = self.build_student_prompt(mcq)
        ground = mcq["validation"]["final_answer"]

        with ThreadPoolExecutor() as exe:
            futures = {exe.submit(self.call_model, m, [{"role": "user", "content": prompt}], img): m for m in STUDENT_MODELS}
            results = []
            for f in futures:
                m = futures[f]
                r = f.result()
                if r["error"]:
                    results.append({"model": m, "answer": None, "reasoning": r["content"], "correct": False, "time_ms": r["time_ms"]})
                    continue
                ans = self.extract_answer(r["content"])
                rea = self.extract_reasoning(r["content"])
                results.append({"model": m, "answer": ans, "reasoning": rea, "correct": (ans == ground), "time_ms": r["time_ms"]})

        acc = sum(1 for x in results if x["correct"]) / len(results) if results else 0
        avg_t = sum(x["time_ms"] for x in results) / len(results) if results else 0

        return {
            "original_mcq_ref": {"problem_id": mcq["problem_id"], "collection": MCQ_COLLECTION},
            "validation": mcq["validation"],
            "student_evaluations": results,
            "question_stats": {"accuracy": round(acc, 3), "avg_time_ms": int(avg_t)}
        }

    # ------------------------------------------------------------------- #
    # RUN TEST
    # ------------------------------------------------------------------- #
    def run_test(self, sample_size: int = 10):
        selected = self.load_mcqs(sample_size)
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        q_results = []

        for i in range(0, len(selected), BATCH_SIZE):
            batch = selected[i:i + BATCH_SIZE]
            print(f"Validating batch {i//BATCH_SIZE + 1} ({len(batch)} questions)")
            resp = self.call_model(MASTER_MODEL, [{"role": "user", "content": self.build_validation_prompt(batch)}])
            if resp["error"]:
                print(f"Validation failed: {resp['content']}")
                continue
            vals = self.parse_validation(resp["content"])
            if len(vals) != len(batch):
                print(f"Validation mismatch: got {len(vals)}, expected {len(batch)}")
                continue
            for mcq, val in zip(batch, vals):
                mcq = self.apply_validation(mcq.copy(), val)
                q_results.append(self.evaluate_question(mcq))
            time.sleep(1)

        # --- SAFE SUMMARY ---
        if not q_results:
            print("No questions passed validation.")
            eval_doc = {
                "test_run_id": run_id,
                "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
                "mode": self.mode,
                "sampler": self.sampler,
                "batch_size": len(selected),
                "validation_model": MASTER_MODEL,
                "student_models": STUDENT_MODELS,
                "shuffle_enabled": SHUFFLE_CHOICES,
                "questions": [],
                "summary": {"overall_accuracy": 0.0, "avg_question_time_ms": 0},
                "error": "All validation batches failed",
                "metadata": {"schema_version": "eval-run-1.0"}
            }
        else:
            overall_acc = sum(q["question_stats"]["accuracy"] for q in q_results) / len(q_results)
            avg_time = sum(q["question_stats"]["avg_time_ms"] for q in q_results) / len(q_results)
            eval_doc = {
                "test_run_id": run_id,
                "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
                "mode": self.mode,
                "sampler": self.sampler,
                "batch_size": len(selected),
                "validation_model": MASTER_MODEL,
                "student_models": STUDENT_MODELS,
                "shuffle_enabled": SHUFFLE_CHOICES,
                "questions": q_results,
                "summary": {"overall_accuracy": round(overall_acc, 3), "avg_question_time_ms": int(avg_time)},
                "metadata": {"schema_version": "eval-run-1.0"}
            }

        self.save_evaluation(eval_doc)
        print(f"Run complete: {run_id}")
        return eval_doc


# --------------------------------------------------------------------------- #
# RUN
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    evaluator = MathLabsEvaluator()  # default: test + random
    evaluator.run_test(sample_size=10)