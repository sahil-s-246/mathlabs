import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from huggingface_hub import HfApi

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
print("🧭 Script located at:", BASE_DIR)
print("🔍 Looking for .env at:", BASE_DIR / ".env")
print("📁 .env exists:", (BASE_DIR / ".env").exists())

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)
print("MONGO_URI loaded as:", repr(os.getenv("MONGO_URI")))



# ---------------------------------------------------------
# 1. Load environment variables
# ---------------------------------------------------------
from pathlib import Path



MONGO_URI = os.getenv("MONGO_URI")
HF_TOKEN = os.getenv("HF_TOKEN")

if not MONGO_URI:
    raise ValueError("❌ Missing MONGO_URI in .env")

api = HfApi(token=HF_TOKEN)


# ---------------------------------------------------------
# 2. Connect to MongoDB
# ---------------------------------------------------------
client = MongoClient(MONGO_URI)
db = client["mathlabs"]

questions_col = db["questions"]
evals_col = db["evaluations"]


# ---------------------------------------------------------
# 3. Load HuggingFace image list
# ---------------------------------------------------------
DATASET_ID = "brucezhang41/MathLABS"

hf_files = api.list_repo_files(repo_id=DATASET_ID, repo_type="dataset")
hf_images = set(
    f.replace("images/", "")
    for f in hf_files
    if f.startswith("images/")
)


# ---------------------------------------------------------
# 4. Load latest evaluation document
# ---------------------------------------------------------
latest_eval = evals_col.find_one({}, sort=[("_id", -1)])

if not latest_eval:
    raise ValueError("❌ No evaluation found in MongoDB")

eval_ids = set()
for block in latest_eval["questions"]:
    ref = block.get("original_mcq_ref", {})
    pid = ref.get("problem_id")
    if pid:
        eval_ids.add(pid)


# ---------------------------------------------------------
# 5. Load all questions from MongoDB
# ---------------------------------------------------------
mongo_ids = set(
    q["problem_id"]
    for q in questions_col.find({}, {"problem_id": 1})
)

# Map problem_id → image_path
pid_to_img = {}
for q in questions_col.find({}, {"problem_id": 1, "diagram_data": 1}):
    pid = q["problem_id"]
    img = q.get("diagram_data", {}).get("image_path")
    if img:
        img = img.replace("images/", "")
    pid_to_img[pid] = img


# ---------------------------------------------------------
# 6. Diagnostics logic
# ---------------------------------------------------------

# A. evaluation → reference missing in MongoDB
missing_in_mongo = sorted(eval_ids - mongo_ids)

# B. evaluation → missing HF image
missing_images = []
for pid in eval_ids:
    img = pid_to_img.get(pid)
    if not img:
        missing_images.append((pid, "(no image_path)"))
    elif img not in hf_images:
        missing_images.append((pid, img))

# C. Fully valid
fully_valid = sorted(
    pid for pid in eval_ids
    if pid in mongo_ids and pid_to_img.get(pid) in hf_images
)


# ---------------------------------------------------------
# 7. Write diagnostics_report.txt
# ---------------------------------------------------------
report_path = "diagnostics_report.txt"

with open(report_path, "w", encoding="utf-8") as f:
    f.write("=== MathLabs Diagnostic Report ===\n\n")

    f.write(f"Total evaluation questions: {len(eval_ids)}\n")
    f.write(f"Total MongoDB questions: {len(mongo_ids)}\n")
    f.write(f"Total HF images: {len(hf_images)}\n\n")

    # A
    f.write("\n--- A. Evaluation references missing in MongoDB ---\n")
    if missing_in_mongo:
        for pid in missing_in_mongo:
            f.write(f"- {pid}\n")
    else:
        f.write("✔ All evaluation ids exist in MongoDB.\n")

    # B
    f.write("\n--- B. Evaluation references missing HF images ---\n")
    if missing_images:
        for pid, img in missing_images:
            f.write(f"- {pid} → missing: {img}\n")
    else:
        f.write("✔ All evaluation images found on HuggingFace.\n")

    # C
    f.write("\n--- C. Fully valid questions (Mongo + Image OK) ---\n")
    for pid in fully_valid:
        f.write(f"- {pid}\n")

    f.write("\n=== End of Report ===\n")

print("📄 diagnostics_report.txt generated.")
print(f"Evaluation IDs: {len(eval_ids)}")
print(f"Missing in Mongo: {len(missing_in_mongo)}")
print(f"Missing HF images: {len(missing_images)}")
print(f"Fully valid: {len(fully_valid)}")
