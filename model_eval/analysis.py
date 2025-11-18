import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os


# --- 1. Robust JSON Loader (Handles both Raw and Clean JSON) ---
def parse_value(value):
    """Extracts numbers from MongoDB style or standard JSON."""
    if isinstance(value, dict):
        if '$numberInt' in value: return int(value['$numberInt'])
        if '$numberDouble' in value: return float(value['$numberDouble'])
    return value


file_path = 'sample_eval.json'

if not os.path.exists(file_path):
    print(f"❌ Error: '{file_path}' not found.")
    exit()

with open(file_path, 'r') as f:
    data = json.load(f)

# --- 2. Build the DataFrame from Scratch ---
records = []
print("📊 Processing data...")

for q_idx, question in enumerate(data.get('questions', [])):
    for eval_entry in question.get('student_evaluations', []):
        # Extract data carefully
        model = eval_entry.get('model', 'Unknown').split(':')[0]  # Shorten name
        is_correct = eval_entry.get('correct', False)

        # Handle time parsing safely
        raw_time = eval_entry.get('time_ms', 0)
        time_ms = parse_value(raw_time)

        records.append({
            "Question_Index": q_idx + 1,
            "Model": model,
            "Correct": is_correct,
            "Time_Seconds": time_ms / 1000.0
        })

df = pd.DataFrame(records)

# --- 3. Generate Aggregates ---
# Leaderboard Stats
model_stats = df.groupby('Model').agg(
    Accuracy=('Correct', 'mean'),
    Latency=('Time_Seconds', 'mean')
).reset_index()

model_stats['Accuracy'] = model_stats['Accuracy'] * 100

# Calculate Rubric Score (Acc - 1.5x Latency)
model_stats['Rubric_Score'] = model_stats['Accuracy'] - (model_stats['Latency'] * 1.5)
model_stats['Rubric_Score'] = model_stats['Rubric_Score'].clip(lower=0)
model_stats = model_stats.sort_values('Rubric_Score', ascending=False)

# Question Difficulty Stats
q_stats = df.groupby('Question_Index')['Correct'].mean() * 100

# --- 4. Plotting ---
plt.style.use('ggplot')

# Plot A: Leaderboard
plt.figure(figsize=(10, 6))
bar_width = 0.35
x = range(len(model_stats))

plt.bar(x, model_stats['Accuracy'], width=bar_width, label='Accuracy (%)', color='#4CAF50')
plt.bar([i + bar_width for i in x], model_stats['Rubric_Score'], width=bar_width, label='Rubric Score', color='#2196F3')

plt.xlabel('Model', fontweight='bold')
plt.ylabel('Score')
plt.title('🏆 Model Leaderboard', pad=15)
plt.xticks([i + bar_width / 2 for i in x], model_stats['Model'], rotation=15)
plt.legend()
plt.tight_layout()
plt.savefig('graph_leaderboard.png')
print("✅ Generated: graph_leaderboard.png")

# Plot B: Efficiency (Latency vs Accuracy)
plt.figure(figsize=(9, 6))
sns.scatterplot(data=model_stats, x='Latency', y='Accuracy', s=400, hue='Model', palette='deep', legend=False)

for i, row in model_stats.iterrows():
    plt.text(row['Latency'], row['Accuracy'] + 2, row['Model'],
             ha='center', fontsize=10, fontweight='bold')

plt.title('⚡ Efficiency Frontier', pad=15)
plt.xlabel('Avg Latency (s) [Lower is Better]')
plt.ylabel('Accuracy (%)')
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.savefig('graph_efficiency.png')
print("✅ Generated: graph_efficiency.png")

# Plot C: Question Difficulty
plt.figure(figsize=(10, 5))
colors = ['#FF5252' if x < 50 else '#FFC107' if x < 75 else '#66BB6A' for x in q_stats.values]

plt.bar(q_stats.index.astype(str), q_stats.values, color=colors)
plt.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='50% Threshold')

plt.title('🧩 Question Difficulty (Red = Hard)', pad=15)
plt.xlabel('Question #')
plt.ylabel('Pass Rate (%)')
plt.tight_layout()
plt.savefig('graph_difficulty.png')
print("✅ Generated: graph_difficulty.png")