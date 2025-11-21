#!/usr/bin/env python3
"""
MathLabs Evaluator – HYBRID (OpenRouter + Hugging Face)
Schema Version: eval-run-1.0 (Perfect Match)
"""

import os
import json
import time
import re
import base64
import random
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI

load_dotenv()

# --------------------------------------------------------------------------- #
# CONFIG & CLIENTS
# --------------------------------------------------------------------------- #
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

if not GEMINI_API_KEY: raise RuntimeError("Set GEMINI_API_KEY in .env")
if not OPENROUTER_API_KEY: raise RuntimeError("Set OPENROUTER_API_KEY in .env")
if not HF_TOKEN: raise RuntimeError("Set HF_TOKEN in .env")

# 1. Gemini Master (Validator)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash")

# 2. OpenRouter Client (Students A)
client_openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# 3. Hugging Face Client (Students B)
client_hf = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN
)

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "mathlabs"
MCQ_COLLECTION = "questions"
EVAL_COLLECTION = "evaluations"
IMAGE_DIR = "/Users/lucasyao/Documents/GitHub/mathlabs/dataset/images"

# --------------------------------------------------------------------------- #
# MODEL DEFINITIONS
# --------------------------------------------------------------------------- #

# List A: The OpenRouter Models
OPENROUTER_MODELS = [
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "qwen/qwen2.5-vl-32b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "nvidia/nemotron-nano-12b-v2-vl:free"
]

# List B: The Hugging Face Router Models
HF_MODELS = [
    "google/gemma-3-27b-it:nebius",
    "Qwen/Qwen2.5-VL-7B-Instruct:hyperbolic",
    "baidu/ERNIE-4.5-VL-28B-A3B-PT:novita",
    "CohereLabs/command-a-vision-07-2025:cohere",
    "zai-org/GLM-4.1V-9B-Thinking:novita"
]

BATCH_SIZE = 2
SHUFFLE_CHOICES = True

# --------------------------------------------------------------------------- #
# EVALUATOR CLASS
# --------------------------------------------------------------------------- #
class MathLabsEvaluator:
    def __init__(self, mode: str = "test", sampler: str = "random"):
        self.mode = mode.lower()
        self.sampler = sampler.lower()

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
            print(f"Selected {len(selected)} questions")
            return selected
        return []

    # ------------------------------------------------------------------- #
    # SAVE
    # ------------------------------------------------------------------- #
    def save_evaluation(self, eval_doc: Dict):
        if self.mode == "db":
            self.evals.update_one(
                {"test_run_id": eval_doc["test_run_id"]},
                {"$set": eval_doc},
                upsert=True
            )
            print(f"Saved to MongoDB: {eval_doc['test_run_id']}")

    # ------------------------------------------------------------------- #
    # GENERIC API CALLER
    # ------------------------------------------------------------------- #
    def _call_openai_compatible_api(self, client: OpenAI, model: str, prompt: str, image_path: Optional[str]) -> Dict:
        messages = []
        content_payload = [{"type": "text", "text": prompt}]

        if image_path:
            full_path = os.path.join(IMAGE_DIR, os.path.basename(image_path))
            try:
                with open(full_path, "rb") as f:
                    b64_img = base64.b64encode(f.read()).decode("utf-8")
                    mime = "image/png" if full_path.endswith(".png") else "image/jpeg"
                    content_payload.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64_img}"}
                    })
            except Exception as e:
                print(f"  [Image Error] {e}")

        messages = [{"role": "user", "content": content_payload}]

        start = time.time()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.1
            )
            ms = int((time.time() - start) * 1000)
            return {"error": False, "content": response.choices[0].message.content, "time_ms": ms}
        
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg:
                print(f"  [429 Limit] {model} is busy.")
            return {"error": True, "content": err_msg, "time_ms": 0}

    # ------------------------------------------------------------------- #
    # VALIDATION (GEMINI)
    # ------------------------------------------------------------------- #
    def gemini_validate_batch(self, batch: List[Dict]) -> List[Dict]:
        prompt_parts = ["Return JSON array with objects {final_answer, difficulty, shuffle, issues}."]
        for i, q in enumerate(batch):
            choices = "\n".join(f"{c['id']}) {c['text']}" for c in q["choices"])
            prompt_parts.append(f"Q{i} ID:{q['problem_id']}\n{q['statement']}\n{choices}\nClaimed:{q['answer']['correct_ids'][0]}")
        
        prompt = "\n".join(prompt_parts)
        contents = [prompt]

        for q in batch:
            img_path = q.get("diagram_data", {}).get("image_path")
            if img_path:
                full_path = os.path.join(IMAGE_DIR, os.path.basename(img_path))
                if os.path.exists(full_path):
                    contents.append(genai.upload_file(full_path))

        try:
            response = gemini_model.generate_content(contents)
            m = re.search(r"\[.*\]", response.text, re.DOTALL)
            return json.loads(m.group(0)) if m else []
        except Exception as e:
            print(f"Gemini Error: {e}")
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

        shuffle_applied = False
        if SHUFFLE_CHOICES and val.get("shuffle", False):
            random.shuffle(mcq["choices"])
            shuffle_applied = True
            
        mcq["validation"] = {
            "validated_by": "gemini-2.5-flash",
            "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            "original_answer": orig_ans,
            "final_answer": val["final_answer"],
            "original_difficulty": orig_diff,
            "final_difficulty": val["difficulty"],
            "shuffle_applied": shuffle_applied,
            "issues": val.get("issues", [])
        }
        return mcq

    # ------------------------------------------------------------------- #
    # EVALUATE SINGLE QUESTION
    # ------------------------------------------------------------------- #
    def evaluate_question(self, mcq: Dict) -> Dict:
        prompt = f"Answer this MCQ.\n\n{mcq['statement']}\n\n" + "\n".join(f"{c['id']}) {c['text']}" for c in mcq["choices"]) + "\n\nANSWER: <letter>\nREASONING: <text>"
        img = mcq.get("diagram_data", {}).get("image_path")
        ground = mcq["answer"]["correct_ids"][0]
        
        results = []
        print(f"  Eval: {mcq['problem_id']}...")

        # Loop A (OpenRouter)
        for m in OPENROUTER_MODELS:
            r = self._call_openai_compatible_api(client_openrouter, m, prompt, img)
            self._process_result(r, m, ground, results)
            time.sleep(2)

        # Loop B (Hugging Face)
        for m in HF_MODELS:
            r = self._call_openai_compatible_api(client_hf, m, prompt, img)
            self._process_result(r, m, ground, results)
            time.sleep(2)

        acc = sum(1 for x in results if x["correct"]) / len(results) if results else 0
        avg_time = int(sum(x["time_ms"] for x in results) / len(results)) if results else 0

        return {
            "original_mcq_ref": {
                "problem_id": mcq["problem_id"],
                "collection": MCQ_COLLECTION
            },
            "validation": mcq["validation"],
            "student_evaluations": results,
            "question_stats": {
                "accuracy": acc,
                "avg_time_ms": avg_time
            }
        }

    def _process_result(self, r, model_name, ground, results_list):
        if r["error"]:
            results_list.append({"model": model_name, "correct": False, "reasoning": r["content"], "time_ms": 0})
        else:
            text = r["content"]
            m = re.search(r"ANSWER:\s*([A-D])", text, re.I)
            ans = m.group(1).upper() if m else None
            m2 = re.search(r"REASONING:\s*(.+)", text, re.I | re.S)
            rea = (m2.group(1).strip() if m2 else text)[:500]
            
            results_list.append({
                "model": model_name,
                "answer": ans,
                "correct": (ans == ground),
                "reasoning": rea,
                "time_ms": r["time_ms"]
            })

    # ------------------------------------------------------------------- #
    # MAIN RUN LOOP
    # ------------------------------------------------------------------- #
    def run_test(self, sample_size=4):
        selected = self.load_mcqs(sample_size)
        run_id = f"run_hybrid_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        full_results = []
        
        for i in range(0, len(selected), BATCH_SIZE):
            batch = selected[i:i + BATCH_SIZE]
            print(f"Processing Batch {i//BATCH_SIZE + 1}...")
            
            vals = self.gemini_validate_batch(batch)
            
            for mcq, val in zip(batch, vals):
                mcq = self.apply_validation(mcq, val)
                res = self.evaluate_question(mcq)
                full_results.append(res)

        overall_acc = sum(q["question_stats"]["accuracy"] for q in full_results) / len(full_results) if full_results else 0
        overall_time = sum(q["question_stats"]["avg_time_ms"] for q in full_results) / len(full_results) if full_results else 0

        # ===========================================================
        # THIS IS WHERE WE MATCH THE SCHEMA
        # ===========================================================
        doc = {
            "test_run_id": run_id,
            "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
            "mode": self.mode,
            "sampler": self.sampler,
            "batch_size": len(selected),
            
            # 1. RESTORE 'shuffle_enabled' at Root
            "shuffle_enabled": SHUFFLE_CHOICES,
            
            # 2. RESTORE 'student_models' List at Root (Combined)
            "student_models": OPENROUTER_MODELS + HF_MODELS,
            
            # 3. RESTORE 'validation_model' at Root
            "validation_model": "gemini-2.5-flash",
            
            "metadata": {
                "schema_version": "eval-run-1.0"
            },
            "questions": full_results,
            "summary": {
                "overall_accuracy": round(overall_acc, 3),
                "avg_question_time_ms": int(overall_time)
            }
        }
        
        self.save_evaluation(doc)
        print(f"\nDone! Saved run: {run_id}")

if __name__ == "__main__":
    evaluator = MathLabsEvaluator(mode="db", sampler="random")
    evaluator.run_test(sample_size=4)