import os
from collections import defaultdict, Counter
from dotenv import load_dotenv
from pymongo import MongoClient

# ---------------------------------------------------------
# 1. Load .env
# ---------------------------------------------------------
load_dotenv(".env")
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("❌ Missing MONGO_URI in .env")

client = MongoClient(MONGO_URI)
db = client["mathlabs"]
evals_col = db["evaluations"]

# ---------------------------------------------------------
# 2. Initialize counters
# ---------------------------------------------------------
pid_counter = Counter()          # problem_id → count
model_counter = Counter()        # model_name → count
batch_ids = []                   # list of test_run_id

# ---------------------------------------------------------
# 3. Scan all evaluation documents
# ---------------------------------------------------------
all_evals = list(evals_col.find({}))

for doc in all_evals:
    test_id = doc.get("test_run_id", "(no test_run_id)")
    batch_ids.append(test_id)

    questions = doc.get("questions", [])

    for q in questions:

        # --- Count problem_id ---
        pid = q.get("original_mcq_ref", {}).get("problem_id")
        if pid:
            pid_counter[pid] += 1

        # --- Count student model usage ---
        students = q.get("student_evaluations", [])
        for stu in students:
            model = stu.get("model")
            if model:
                model_counter[model] += 1


# ---------------------------------------------------------
# 4. Sort statistics
# ---------------------------------------------------------
sorted_pids = pid_counter.most_common()
sorted_models = model_counter.most_common()

# ---------------------------------------------------------
# 5. Write to evaluation_stats.txt
# ---------------------------------------------------------
report_path = "evaluation_stats.txt"

with open(report_path, "w", encoding="utf-8") as f:

    f.write("=== MathLabs Evaluation Statistics ===\n\n")

    f.write(f"Total evaluation batches: {len(all_evals)}\n")
    f.write(f"Total unique problem_ids: {len(pid_counter)}\n")
    f.write(f"Total unique models: {len(model_counter)}\n\n")

    f.write("\n--- Unique test_run_ids (batches) ---\n")
    for bid in batch_ids:
        f.write(f"- {bid}\n")

    f.write("\n--- Problem Frequency (problem_id → number of times evaluated) ---\n")
    for pid, count in sorted_pids:
        f.write(f"{pid}: {count}\n")

    f.write("\n--- Model Frequency (model → number of uses) ---\n")
    for model, count in sorted_models:
        f.write(f"{model}: {count}\n")

    f.write("\n=== End of Report ===\n")

print("📄 evaluation_stats.txt generated.")
print(f"Unique problems: {len(pid_counter)}")
print(f"Unique models:   {len(model_counter)}")
