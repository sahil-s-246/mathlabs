import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

# 2. Get URI from .env (SAFER)
# Make sure your .env has: MONGO_URI=mongodb+srv://demo:PASSWORD@mathlabs.hg7sdxp.mongodb.net/mathlabs
uri = os.getenv("MONGO_URI")

if not uri:
    print("❌ Error: MONGO_URI not found in .env file.")
    exit()

# 3. Correct Connection Logic
try:
    client = MongoClient(uri)
    
    # We explicitly select the 'mathlabs' database
    db = client["mathlabs"] 
    
    # We select the 'evaluations' collection
    evals = db["evaluations"] 
    
    print(f"🔌 Connected to database: {db.name}")
    print(f"📂 Collection: {evals.name}")

except Exception as e:
    print(f"❌ Connection Error: {e}")
    exit()

run_id = "run_hybrid_20251119_1647"

# 4. The Logic (Cleaned up)
doc = evals.find_one({"test_run_id": run_id})

if doc:
    print(f"✅ Found run: {run_id}. Fixing schema...")
    new_questions = []
    
    for q in doc["questions"]:
        # Fix Reference
        problem_id = q.get("problem_id")
        
        # Fix Validation
        validation = {
            "validated_by": "gemini-2.5-flash",
            "validated_at": datetime.now(),
            "original_answer": "A", 
            "final_answer": "A",
            "original_difficulty": "unknown",
            "final_difficulty": "unknown",
            "shuffle_applied": False,
            "issues": []
        }

        # Calculate Avg Time (Handle potential missing keys safely)
        total_ms = 0
        count = 0
        if "student_evaluations" in q:
            count = len(q["student_evaluations"])
            for s in q["student_evaluations"]:
                # Handle raw int or dictionary format safely
                t = s.get("time_ms", 0)
                if isinstance(t, dict) and "$numberInt" in t:
                    total_ms += int(t["$numberInt"])
                else:
                    total_ms += int(t)
        
        avg_ms = int(total_ms / count) if count > 0 else 0

        # Fix Stats
        old_stats = q.get("stats", {})
        new_stats = {
            "accuracy": old_stats.get("accuracy", 0),
            "avg_time_ms": avg_ms
        }

        # Rebuild object
        new_q = {
            "original_mcq_ref": {
                "problem_id": problem_id,
                "collection": "questions"
            },
            "validation": validation,
            "student_evaluations": q.get("student_evaluations", []),
            "question_stats": new_stats
        }
        new_questions.append(new_q)

    # Update DB
    result = evals.update_one(
        {"test_run_id": run_id},
        {
            "$set": {
                "questions": new_questions,
                "metadata": {"schema_version": "eval-run-1.0"},
                "mode": "db",
                "sampler": "sequential"
            },
            "$unset": { "stats": "" } # Clean up old field
        }
    )
    print(f"🎉 Successfully fixed schema for {run_id}")
    print(f"   Modified {result.modified_count} document.")
else:
    print(f"❌ Run ID '{run_id}' not found in collection '{evals.name}'")