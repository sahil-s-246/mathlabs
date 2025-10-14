import json

# Path to the JSON file
file_path = "dataset/baseline_sahil.json"

# Define the new source format
new_source = {
    "type": "extract",
    "book_title": "Discrete Mathematics and Its Applications",
    "authors": [
        "Kenneth Rosen"
    ],
    "edition": None,
    "chapter": None,
    "page": None,
    "exercise_number": None
}

# Read the JSON file
with open(file_path, "r", encoding="utf-8") as file:
    data = json.load(file)

# Update the source key for all objects except the first one
for i, obj in enumerate(data):
    if i != 0:  # Skip the first object
        obj["source"] = new_source

# Write the updated JSON back to the file
with open(file_path, "w", encoding="utf-8") as file:
    json.dump(data, file, indent=4)

print(f"Updated {file_path}. First object remains unchanged, and source updated for others.")