#!/usr/bin/env python3
"""
MathLabs Generator – RANDOM-PER-IMAGE (1 image → 5 new MCQs)
- Switches to Google Gemini 1.5 Flash (fast + cheap)
- Samples N *different* baseline images/questions OR N *fresh* images from a library
- Sends ONE API call per image, generates 5 new MCQs each
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
FRESH_IMAGE_DIR = "./library"  # Folder for image-only generation
OUTPUT_JSON_FILE = "generated_mcqs.json"
MASTER_MODEL = "gemini-2.5-flash"
NUM_BASELINES = 3           # Max number of images to sample (applies to both modes)
NUM_PER_IMAGE = 5
MAX_QUESTIONS = 15          # Target total questions
DIFFICULTY_LEVELS = ["easy", "medium"]
TOPICS = [
    "linear_algebra", "calculus", "probability", "graph_theory", "number_theory",
    "geometry", "discrete_mathematics", "statistics", "combinatorics"
]
VALID_IMG_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp') # Define image extensions once

# --------------------------------------------------------------------------- #
# GENERATOR CLASS
# --------------------------------------------------------------------------- #
class MathLabsGenerator:
    def __init__(self, msc_filter: str = None):
        """
        Initializes the generator and loads baseline candidates, optionally filtered by MSC prefix.
        Args:
            msc_filter (str): Optional MSC prefix (e.g., '15') to filter baseline questions.
        """
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            MASTER_MODEL,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json"  # forces pure JSON
            )
        )
        self.candidates = self._load_all_baseline_candidates(msc_prefix=msc_filter)
        if not self.candidates:
            if msc_filter:
                 print(f"Warning: No baseline question found for MSC prefix '{msc_filter}'. Fresh mode can still be used.")
            else:
                print("Warning: No baseline question with a valid image was found. Fresh mode can still be used.")
        else:
            print(f"Found {len(self.candidates)} baseline questions with usable images.")

    
    # ------------------------------------------------------------------- #
    def _load_all_baseline_candidates(self, msc_prefix: str = None) -> List[Tuple[str, Dict, str, str]]:
        """Loads all baseline candidates, filtering by MSC prefix if provided."""
        all_candidates = []
        global BASELINE_JSON_FILES 
        
        for json_file in BASELINE_JSON_FILES:
            if not os.path.exists(json_file):
                print(f"Warning: Baseline file not found: {json_file}. Skipping.")
                continue

            file_prefix = os.path.splitext(os.path.basename(json_file))[0]
            
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                
                if isinstance(raw, list):
                    items = [(f"{file_prefix}_base-{i+1:03d}", q) for i, q in enumerate(raw)]
                else:
                    items = [(f"{file_prefix}_{k}", v) for k, v in raw.items() if k != "schema_version"]
                
                for pid, q in items:
                    
                    problem_identifier = q.get("problem_id", pid)
                    if msc_prefix and not problem_identifier.startswith(msc_prefix):
                        continue

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
                print(f"Error loading {json_file}: {e}")
                
        return all_candidates

    # ------------------------------------------------------------------- #
    def _sample_fresh_image(self) -> List[Tuple[str, str, str]]:
        """
        Samples images from FRESH_IMAGE_DIR (library) for fresh generation.
        Returns: [(pseudo_pid, filename, full_image_path), ...]
        """
        if not os.path.isdir(FRESH_IMAGE_DIR):
            raise FileNotFoundError(f"Fresh image directory not found: {FRESH_IMAGE_DIR}")

        # List all image files
        all_files = [f for f in os.listdir(FRESH_IMAGE_DIR) 
                     if os.path.isfile(os.path.join(FRESH_IMAGE_DIR, f)) and f.lower().endswith(VALID_IMG_EXTENSIONS)]
        
        if not all_files:
            raise RuntimeError(f"No usable images found in {FRESH_IMAGE_DIR}")
        
        # Sample up to NUM_BASELINES images
        selected_files = random.sample(all_files, min(NUM_BASELINES, len(all_files)))
        
        results = []
        for f in selected_files:
            img_path = os.path.join(FRESH_IMAGE_DIR, f)
            # Use the cleaned filename prefix as the base PID
            pid = os.path.splitext(f)[0] 
            results.append((pid, f, img_path))
            
        return results

    # ------------------------------------------------------------------- #
    def build_contents(self, example_q: Dict, img_path: str, filename: str,
                         num_questions: int, difficulty: str, topics: List[str]) -> List[Any]:
        """Builds contents for VARIATION mode (based on existing question/JSON)."""
        img = Image.open(img_path)
        topic_list = ", ".join(topics or random.sample(TOPICS, 3))

        # Variation Mode Prompt: Reuses example context but focuses on image data
        few_shot = f"""**EXAMPLE CONTEXT (reuse all relevant concepts/data/text):**
{json.dumps(example_q, indent=2)}"""

        instruction = f"""
You are a world-class math MCQ generator.

CRITICAL RULES (follow exactly or you fail):
1. You just saw ONE diagram (the image above).
2. EVERY new question MUST set "image_path": "{filename}" (exact string, no changes).
3. Questions must be **COMPLETELY NEW** but MUST **DEPEND** on the same visible diagram elements/data.
4. If the provided EXAMPLE CONTEXT is mainly prose/text without a specific calculation, generate a new, relevant question based *primarily* on the image content.
5. Use only {difficulty} difficulty.
6. Never use null for image_path.
7. Output EXACTLY {num_questions} questions with keys "gen-001" → "gen-{num_questions:03d}".
8. **CRITICAL JSON RULE: All string values must be valid. Escape ALL internal double-quotes with \\" and ALL newlines with \\n.**
9. **CRITICAL CONTENT RULE: The new question MUST use the diagram/image content as the primary basis for the problem.**
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
    def build_contents_fresh(self, img_path: str, filename: str,
                             num_questions: int, difficulty: str, topics: List[str]) -> List[Any]:
        """Builds contents for FRESH mode (image-only generation)."""
        img = Image.open(img_path)
        topic_list = ", ".join(topics or random.sample(TOPICS, 3))

        instruction = f"""
You are a world-class math MCQ generator.

CRITICAL RULES (follow exactly or you fail):
1. You just saw ONE diagram (the image above).
2. The image is the *only* context. Analyze it completely and generate problems based *only* on the visual information.
3. EVERY new question MUST set "image_path": "{filename}" (exact string, no changes).
4. Questions must be **COMPLETELY NEW** and MUST **DEPEND** on the visual diagram elements/data.
5. Use only {difficulty} difficulty.
6. Never use null for image_path.
7. Output EXACTLY {num_questions} questions with keys "gen-001" → "gen-{num_questions:03d}".
8. **CRITICAL JSON RULE: All string values must be valid. Escape ALL internal double-quotes with \\" and ALL newlines with \\n.**
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
        return [img, instruction]

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
    def save_mcqs(self, mcqs: Dict[str, Dict], run_id: str):
        """Write a dedicated JSON file for this run and (optionally) append to master."""
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"

        # 1. Per-run file (with generated questions having enforced structure)
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
            
            # Force Source Type and Model
            q["source"] = {
                "type": "generate",
                "model": MASTER_MODEL
            }
            
            existing[pid] = q

        master_data = {"schema_version": "mcq-1.0"}
        master_data.update(existing)
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        print(f"Master updated → {master_path} (total {len(existing)})")

    # ------------------------------------------------------------------- #
    def run_generation(self, target_questions: int = MAX_QUESTIONS, fresh: bool = False):
        """
        Runs the generation process.
        Args:
            target_questions (int): The total number of questions to generate.
            fresh (bool): If True, generate questions from random library images (image-only mode).
                          If False, generate variations from baseline JSONs (variation mode).
        """
        run_id = f"gen_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        all_mcqs: Dict[str, Dict] = {}
        
        # --- LOGIC SWITCH BASED ON 'fresh' PARAMETER ---
        if fresh:
            print("--- Running in FRESH IMAGE MODE (Image-Only Generation) ---")
            selected_images_info = self._sample_fresh_image()
            # Structure for fresh mode: (pid, filename, img_path) -> (pid, empty_dict, filename, img_path)
            image_iterator = [(info[0], {}, info[1], info[2]) for info in selected_images_info]
        elif not self.candidates:
            raise RuntimeError("Cannot run in VARIATION mode: No baseline questions were loaded. Set 'fresh=True' or fix baseline files.")
        else:
            print("--- Running in VARIATION MODE (Baseline-based Generation) ---")
            # Structure for Variation mode: (baseline_pid, example_q, filename, img_path)
            selected_candidates = random.sample(self.candidates, min(NUM_BASELINES, len(self.candidates)))
            image_iterator = selected_candidates

        print(f"Selected {len(image_iterator)} distinct images for generation.\n")
        # --- END LOGIC SWITCH ---

        for idx, (base_pid, example_q, filename, img_path) in enumerate(image_iterator, 1):
            difficulty = random.choice(DIFFICULTY_LEVELS)
            topics = random.sample(TOPICS, 3)
            mode_tag = "FRESH" if fresh else "VARIATION"
            print(f"[{idx}/{len(image_iterator)}] Generating {NUM_PER_IMAGE} MCQs ({mode_tag}) with `{filename}` (difficulty: {difficulty})")

            if fresh:
                # Use the new prompt builder for fresh images
                contents = self.build_contents_fresh(
                    img_path=img_path,
                    filename=filename,
                    num_questions=NUM_PER_IMAGE,
                    difficulty=difficulty,
                    topics=topics
                )
            else:
                # Use the original prompt builder for variations
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
            
            # Make keys unique
            file_prefix = os.path.splitext(filename)[0]
            timestamp_suffix = datetime.now().strftime('%f')
            renamed_mcqs = {}
            for key, q in parsed.items():
                # Format: [FilePrefix]_[gen-001]_[MicrosecondTimestamp]
                new_key = f"{file_prefix}_{key}_{timestamp_suffix}"
                renamed_mcqs[new_key] = q

            all_mcqs.update(renamed_mcqs)

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
    
    # Check if all specified baseline files exist
    for f in BASELINE_JSON_FILES:
        if not os.path.exists(f):
            raise FileNotFoundError(f"Baseline file missing: {f}")
    
    # --- CONFIGURE RUN MODE ---
    RUN_FRESH_MODE = True
    MSC_TO_FILTER = None 
    
    # Initialize the generator
    gen = MathLabsGenerator(msc_filter=MSC_TO_FILTER)

    # --- NEW: Call the preprocessing function here BEFORE running generation ---
    # This ensures your library images are clean and organized before sampling.
    # Set the prefix to whatever you like (e.g., 'CONCEPT', 'PROOF', etc.)
  
    # --------------------------------------------------------------------------
    
    # Run the generation with the chosen mode
    gen.run_generation(target_questions=MAX_QUESTIONS, fresh=RUN_FRESH_MODE)