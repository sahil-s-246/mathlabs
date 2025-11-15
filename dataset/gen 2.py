#!/usr/bin/env python3
"""
MathLabs Generator – RANDOM-PER-IMAGE (1 image → 5 new MCQs)
- Switches to Google Gemini 1.5 Flash (fast + cheap)
- Samples 3 *different* baseline images/questions
- Sends ONE API call per image, generates 5 new MCQs each (total ~15, easily covers your 10-question goal)
- Reuses the exact same filename + real base64 image
- JSON-only mode + strict prompting → perfect parsing
- Built-in delays → safe for rate-limits
- Cost: ~$0.001–$0.003 per full run (15 questions)
"""
import os
import json
import random
import time
import re
import base64
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
from PIL import Image

# --------------------------------------------------------------------------- #
# CONFIG
# --------------------------------------------------------------------------- #
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Set GEMINI_API_KEY in .env file (get it from https://aistudio.google.com/app/apikey)")

# FULL PATHS
BASELINE_JSON_FILES = [
    "baseline_lucas.json",
    "baseline_bruce.json",
    "baseline_sahil.json"
]
BASE_IMAGE_DIR = "./images"
OUTPUT_JSON_FILE = "generated_mcqs.json"
MASTER_MODEL = "gemini-2.5-flash"  # ← change to "gemini-2.0-flash" if available in 2025
NUM_BASELINES = 10          # we sample 3 different images
NUM_PER_IMAGE = 5
MAX_QUESTIONS = 50# 5 brand-new MCQs per image → ~15 total (covers your 10 easily)
DIFFICULTY_LEVELS = ["easy", "medium"]
TOPICS = [
    "linear_algebra", "calculus", "probability", "graph_theory", "number_theory",
    "geometry", "discrete_mathematics", "statistics", "combinatorics"
]

# --------------------------------------------------------------------------- #
# GENERATOR CLASS
# --------------------------------------------------------------------------- #
class MathLabsGenerator:
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            MASTER_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.7,

                response_mime_type="application/json"  # forces pure JSON
            )
        )
        self.candidates = self._load_all_baseline_candidates()
        if not self.candidates:
            raise RuntimeError("No baseline question with a valid image was found.")
        print(f"Found {len(self.candidates)} baseline questions with usable images.")

    # ------------------------------------------------------------------- #
    # ------------------------------------------------------------------- #
    def _load_all_baseline_candidates(self) -> List[Tuple[str, Dict, str, str]]:
        """
        Loads all baseline candidates from the list of JSON files defined in CONFIG.
        Returns: (unique_pid, question_dict, filename, full_image_path)
        """
        all_candidates = []
        
        # Access the list of files defined in the CONFIG section
        global BASELINE_JSON_FILES 
        
        # Loop through every file in the list
        for json_file in BASELINE_JSON_FILES:
            if not os.path.exists(json_file):
                print(f"Warning: Baseline file not found: {json_file}. Skipping.")
                continue

            # Create a unique prefix for problem IDs (e.g., "lucas_base-001")
            file_prefix = os.path.splitext(os.path.basename(json_file))[0]
            
            try:
                # --- This line opens ONE file at a time, fixing the error ---
                with open(json_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                
                # --- Rest of the logic to extract and collect candidates ---
                if isinstance(raw, list):
                    items = [(f"{file_prefix}_base-{i+1:03d}", q) for i, q in enumerate(raw)]
                else:
                    items = [(f"{file_prefix}_{k}", v) for k, v in raw.items() if k != "schema_version"]
                
                # Process candidates in the current file
                for pid, q in items:
                    full_path = q.get("diagram_data", {}).get("image_path")
                    if not full_path or full_path.lower() == "null":
                        continue
                        
                    filename = os.path.basename(full_path)
                    img_path = os.path.join(BASE_IMAGE_DIR, filename)
                    
                    if os.path.isfile(img_path):
                        q_copy = json.loads(json.dumps(q))
                        q_copy["diagram_data"]["image_path"] = filename
                        all_candidates.append((pid, q_copy, filename, img_path))
                        
            except Exception as e:
                # Catch specific errors during processing of this single file
                print(f"Error loading {json_file}: {e}")
                
        # Return all candidates collected from all files
        return all_candidates

    # ------------------------------------------------------------------- #
    def build_contents(self, example_q: Dict, img_path: str, filename: str,
                         num_questions: int, difficulty: str, topics: List[str]) -> List[Any]:
        img = Image.open(img_path)
        topic_list = ", ".join(topics or random.sample(TOPICS, 3))

        few_shot = f"""**EXAMPLE QUESTION (reuse this EXACT diagram file):**
{json.dumps(example_q, indent=2)}"""

        instruction = f"""
You are a world-class math MCQ generator.

CRITICAL RULES (follow exactly or you fail):
1. You just saw ONE diagram (the image above).
2. EVERY new question MUST set "image_path": "{filename}" (exact string, no changes).
3. Questions must be COMPLETELY NEW but DEPEND on the same visible diagram elements.
4. Use only {difficulty} difficulty.
5. Never use null for image_path.
6. Output EXACTLY {num_questions} questions with keys "gen-001" → "gen-{num_questions:03d}".
7. **CRITICAL JSON RULE: All string values must be valid. Escape ALL internal double-quotes with \\" and ALL newlines with \\n.**
8. **CRITICAL CONTENT RULE: The new question MUST be a variation of the example. If the image contains text, you MUST use that text/concept. If the image shows data (like matrices), you MUST use that data.**
MANDATORY JSON SCHEMA (output ONLY this object, no extra text/markdown):
{{
  "gen-001": {{
    "question_type": "multiple_choice",
    "source": {{ "type": "generate", "model": "{MASTER_MODEL}" }},
    "topic": ["algebra", "geometry"],
    "gradelevel": ["College-level"],
    "statement": "Your LaTeX statement here",
    "diagram_data": {{
      "image_path": "{filename}",
      "alt_text": "Accurate alt-text for screen readers"
    }},
    "choices": [{{"id": "A", "text": "..."}}, {{"id": "B", "text": "..."}}, ...],
    "answer": {{
      "correct_ids": ["B"],
      "explanation": "Step-by-step solution",
      "distractor_rationales": {{"A": "...", "C": "..."}}
    }},
    "difficulty": "{difficulty}",
    "validation_status": "unverified",
    "flags": []
  }},
  "gen-002": {{ ... same structure ... }}
}}

Topics to use (pick 1-3): {topic_list}
Use \\( \\) for inline math, \\[ \\] for display.
Begin now – output ONLY the JSON.
"""
        return [few_shot, img, instruction]

    # ------------------------------------------------------------------- #
    def call_model(self, contents: List[Any]) -> Dict:
        start = time.time()
        try:
            response = self.model.generate_content(contents)
            ms = int((time.time() - start) * 1000)
            return {"error": False, "content": response.text, "time_ms": ms}
        except Exception as e:
            ms = int((time.time() - start) * 1000)
            return {"error": True, "content": str(e), "time_ms": ms}

    # ------------------------------------------------------------------- #
    def parse_generated_mcqs(self, text: str) -> Dict[str, Any]:
        # Gemini JSON mode → usually clean, fallback to regex
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k != "schema_version" and isinstance(v, dict)}
            return {}
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return {}

    # ------------------------------------------------------------------- #
    # def save_mcqs(self, mcqs: Dict[str, Dict], run_id: str):
    #     timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    #     output_path = OUTPUT_JSON_FILE
    #     existing = {}
    #     if os.path.exists(output_path):
    #         try:
    #             with open(output_path, "r", encoding="utf-8") as f:
    #                 content = json.load(f)
    #                 if isinstance(content, dict):
    #                     existing = {k: v for k, v in content.items() if k != "schema_version"}
    #         except Exception:
    #             pass
    #     valid = 0
    #     for pid, q in mcqs.items():
    #         if not isinstance(q, dict):
    #             continue
    #         q["problem_id"] = pid
    #         q["generated_at"] = timestamp
    #         q["generation_run_id"] = run_id
    #         # force correct model name
    #         if "source" in q and isinstance(q["source"], dict):
    #             q["source"]["model"] = MASTER_MODEL
    #         existing[pid] = q
    #         valid += 1
    #     out_data = {"schema_version": "mcq-1.0"}
    #     out_data.update(existing)
    #     with open(output_path, "w", encoding="utf-8") as f:
    #         json.dump(out_data, f, indent=2, ensure_ascii=False)
    #     print(f"Saved {valid} new questions (total now {len(existing)}) → {output_path}")

    # ------------------------------------------------------------------- #
    # def run_generation(self, target_questions: int = 10):
    #     run_id = f"gen_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    #     all_mcqs = {}
    #     selected = random.sample(self.candidates, min(NUM_BASELINES, len(self.candidates)))
    #     print(f"Selected {len(selected)} distinct baseline images for generation.\n")
    #
    #     for idx, (baseline_pid, example_q, filename, img_path) in enumerate(selected, 1):
    #         difficulty = random.choice(DIFFICULTY_LEVELS)
    #         topics = random.sample(TOPICS, 3)
    #         print(f"[{idx}/{len(selected)}] Generating {NUM_PER_IMAGE} MCQs with image `{filename}` (difficulty: {difficulty})")
    #
    #         contents = self.build_contents(
    #             example_q=example_q,
    #             img_path=img_path,
    #             filename=filename,
    #             num_questions=NUM_PER_IMAGE,
    #             difficulty=difficulty,
    #             topics=topics
    #         )[0]  # only contents
    #
    #         resp = self.call_model(contents)
    #         if resp["error"]:
    #             print(f"API error: {resp['content']}")
    #             continue
    #
    #         parsed = self.parse_generated_mcqs(resp["content"])
    #         print(f"Parsed {len(parsed)} MCQs from this call.")
    #
    #         all_mcqs.update(parsed)
    #         if len(all_mcqs) >= target_questions:
    #             print(f"Reached {len(all_mcqs)} ≥ {target_questions} questions – stopping early.")
    #             break
    #
    #         time.sleep(6)  # super safe for rate limits (Flash allows 60–2000 QPM)
    #
    #     if all_mcqs:
    #         # trim to exact target if you want exactly 10
    #         if len(all_mcqs) > target_questions:
    #             all_mcqs = dict(list(all_mcqs.items())[:target_questions])
    #         self.save_mcqs(all_mcqs, run_id)
    #         print(f"\nDONE – {len(all_mcqs)} MCQs saved (run {run_id})")
    #     else:
    #         print("No MCQs generated.")
    # ------------------------------------------------------------------- #
    # SAVE – one file *per run* (e.g. gen_20251106_195948.json) + optional master
    # ------------------------------------------------------------------- #
    def save_mcqs(self, mcqs: Dict[str, Dict], run_id: str):
        """Write a dedicated JSON file for this run and (optionally) append to master."""
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"

        # 1. Per-run file
        run_path = f"{run_id}.json"
        run_data = {"schema_version": "mcq-1.0", "run_id": run_id, "generated_at": timestamp}
        run_data.update(mcqs)
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2, ensure_ascii=False)
        print(f"Run file → {run_path} ({len(mcqs)} MCQs)")

        # 2. Optional master file (append mode)
        master_path = OUTPUT_JSON_FILE
        existing = {}
        if os.path.exists(master_path):
            try:
                with open(master_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        existing = {k: v for k, v in content.items()
                                   if k not in ("schema_version", "run_id", "generated_at")}
            except Exception:
                pass

        for pid, q in mcqs.items():
            if not isinstance(q, dict):
                continue
            q["problem_id"] = pid
            q["generated_at"] = timestamp
            q["generation_run_id"] = run_id
            if "source" in q and isinstance(q["source"], dict):
                q["source"]["model"] = MASTER_MODEL
            existing[pid] = q

        master_data = {"schema_version": "mcq-1.0"}
        master_data.update(existing)
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        print(f"Master updated → {master_path} (total {len(existing)})")

    # ------------------------------------------------------------------- #
    # RUN – 3 images → 5 MCQs each → 15 total (trim to target if you want)
    # ------------------------------------------------------------------- #
    def run_generation(self, target_questions: int = 15):
        run_id = f"gen_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        all_mcqs: Dict[str, Dict] = {}

        selected = random.sample(self.candidates, min(NUM_BASELINES, len(self.candidates)))
        print(f"Selected {len(selected)} distinct baseline images for generation.\n")

        for idx, (baseline_pid, example_q, filename, img_path) in enumerate(selected, 1):
            difficulty = random.choice(DIFFICULTY_LEVELS)
            topics = random.sample(TOPICS, 3)
            print(f"[{idx}/{len(selected)}] Generating {NUM_PER_IMAGE} MCQs with `{filename}` "
                  f"(difficulty: {difficulty})")

            contents = self.build_contents(
                example_q=example_q,
                img_path=img_path,
                filename=filename,
                num_questions=NUM_PER_IMAGE,
                difficulty=difficulty,
                topics=topics
            )

            resp = self.call_model(contents)
            if resp["error"]:
                print(f"API error: {resp['content']}")
                continue

            parsed = self.parse_generated_mcqs(resp["content"])
            print(f"Parsed {len(parsed)} MCQs from this call.")
            # --- FIX: Make keys unique before updating ---
            # We rename the keys (e.g., "gen-001") to be unique by
            # adding the filename as a prefix (e.g., "15-023_gen-001").
            file_prefix = os.path.splitext(filename)[0]  # Gets "15-023"
            renamed_mcqs = {}
            for key, q in parsed.items():
                new_key = f"{file_prefix}_{key}_{time.time()}"  # e.g., "15-023_gen-001"
                renamed_mcqs[new_key] = q

            all_mcqs.update(renamed_mcqs)
            # --- END FIX ---

            # Stop early if we already hit the target
            if len(all_mcqs) >= target_questions:
                print(f"Reached {len(all_mcqs)} ≥ {target_questions} – stopping.")
                break

            time.sleep(6)   # safe for Flash rate-limits

        # Trim to exact target (optional)
        if len(all_mcqs) > target_questions:
            all_mcqs = dict(list(all_mcqs.items())[:target_questions])

        if all_mcqs:
            self.save_mcqs(all_mcqs, run_id)
            print(f"\nDONE – {len(all_mcqs)} MCQs saved (run {run_id})")
        else:
            print("No MCQs generated.")
# --------------------------------------------------------------------------- #
# MAIN
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    
    # --- CORRECTED CODE START ---
    # Loop through the list of files and check each one individually
    for f in BASELINE_JSON_FILES:
        if not os.path.exists(f):
            # This handles the case where a single file in the list is missing
            raise FileNotFoundError(f"Baseline file missing: {f}")
    # --- CORRECTED CODE END ---

    # After verifying all files exist, proceed with the generator
    gen = MathLabsGenerator()
    gen.run_generation(target_questions=MAX_QUESTIONS)