# combined_pipeline.py

import os
import json
import time
from pathlib import Path
import dotenv
import google.generativeai as genai
from landingai_ade import LandingAIADE

dotenv.load_dotenv()

# --- Configuration: MSC 2020 Codes ---
MSC_CODE_MAP = {
    "statistics": "62",
    "probability": "60",
    "linear algebra": "15",
    "algebra": "12",
    "geometry": "51",
    "calculus": "26",
    "number theory": "11",
    "combinatorics": "05",
    "decision_theory": "91",
    "default": "00"
}

# --- Configuration: Directories ---
INPUT_IMAGES_DIR = Path("input_images")
PARSED_DOCUMENTS_DIR = Path("parsed_documents")
FINAL_OUTPUT_FILE = "master_dataset_complete.json"
SUPPORTED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif'}


def setup_gemini():
    """Configures the Generative AI model."""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        print(f"Error setting up Gemini: {e}")
        return None


def build_prompt(task, content):
    """Builds a specific prompt for a given task."""
    prompts = {
        "restructure": f"""
        Analyze the raw JSON content below. Extract the problem statement, and infer its source, academic subfield, topics, and grade level.
        **Instructions:**
        1. "statement" should be the core text of the problem.
        2. "subfield" should be a list with ONE primary academic field (e.g., ["Statistics"]).
        3. "topic" should be a list of 2-4 specific topics.
        4. "gradelevel" should be a list with one entry (e.g., ["College-level"]).
        5. "source" should be a JSON object based on the source data.
        6. Format your entire response as a single, valid JSON object.
        **Required JSON Structure:** {{"statement": "...", "source": {{}}, "subfield": [], "topic": [], "gradelevel": []}}
        **Raw Content:** {content}
        **Your JSON Output:**
        """,
        "solution": f"""
        Based on the problem statement, generate 2-3 concise hints and a detailed, step-by-step solution.
        **Instructions:** Format your response as a single, valid JSON object.
        **Required JSON Structure:** {{"hints": ["hint1", "hint2"], "solution": "Detailed solution..."}}
        **Problem Statement:** "{content}"
        **Your JSON Output:**
        """,
        "diagram": f"""
        Analyze the problem statement to determine if a diagram is needed.
        **Instructions:** If needed, provide TikZ code. If not, indicate "none". Format your response as a single, valid JSON object.
        **Required JSON Structure (if needed):** {{"type": "latex_tikz", "code": "..."}}
        **Required JSON Structure (if not needed):** {{"type": "none", "code": ""}}
        **Problem Statement:** "{content}"
        **Your JSON Output:**
        """
    }
    return prompts[task]


def clean_gemini_response(response_text):
    """Removes markdown formatting to isolate the JSON object."""
    json_start = response_text.find('{')
    json_end = response_text.rfind('}')
    return response_text[json_start: json_end + 1] if json_start != -1 and json_end != -1 else "{}"


def parse_documents():
    """
    Step 1: Parse all images/documents using LandingAI ADE.
    """
    print("\n" + "=" * 60)
    print("STEP 1: PARSING DOCUMENTS WITH LANDINGAI ADE")
    print("=" * 60 + "\n")

    PARSED_DOCUMENTS_DIR.mkdir(exist_ok=True)

    # Get all image files from the input directory
    documents = [
        f for f in INPUT_IMAGES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not documents:
        print(f"No supported documents found in '{INPUT_IMAGES_DIR}'")
        print(f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return False

    print(f"Found {len(documents)} documents to process\n")

    # Initialize the ADE client
    ade = LandingAIADE()

    # Process each document
    for i, doc_path in enumerate(documents, 1):
        try:
            print(f"Processing {i}/{len(documents)}: {doc_path.name}")

            # Parse the document
            response = ade.parse(document_url=str(doc_path))

            # Prepare data to save
            result = response.model_dump_json()

            # Create output filename (same name as input)
            output_file = PARSED_DOCUMENTS_DIR / f"{doc_path.stem}.json"

            # Save to JSON file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"✓ Saved to: {output_file.name}\n")

        except Exception as e:
            print(f"✗ Error processing {doc_path.name}: {str(e)}\n")
            continue

    print(f"Document parsing complete! {len(documents)} documents processed.")
    print(f"Results saved in '{PARSED_DOCUMENTS_DIR}' folder.\n")
    return True


def run_master_pipeline():
    """
    Step 2: Process all parsed JSON files to create a complete, structured dataset.
    """
    print("\n" + "=" * 60)
    print("STEP 2: RUNNING MASTER PIPELINE WITH GEMINI")
    print("=" * 60 + "\n")

    model = setup_gemini()
    if not model:
        return False

    all_questions = []
    msc_counters = {}

    print(f"Searching for JSON files in '{PARSED_DOCUMENTS_DIR}'...")

    for root, _, files in os.walk(PARSED_DOCUMENTS_DIR):
        for file_name in files:
            if not file_name.endswith(".json"):
                continue

            file_path = os.path.join(root, file_name)
            print(f"\n--- Processing File: {file_path} ---")

            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    raw_content = f.read()

                final_question = {}

                # --- Step 1: Restructure and get metadata ---
                print("  Step 1: Restructuring and classifying...")
                restructure_prompt = build_prompt("restructure", raw_content)
                response = model.generate_content(restructure_prompt)
                metadata = json.loads(clean_gemini_response(response.text))
                final_question.update(metadata)
                time.sleep(1)

                # --- Step 2: Generate problem_id ---
                print("  Step 2: Generating problem ID...")
                subfield = final_question.get("subfield", ["default"])[0].lower()
                msc_code = MSC_CODE_MAP.get(subfield, MSC_CODE_MAP["default"])
                count = msc_counters.get(msc_code, 0) + 1
                msc_counters[msc_code] = count
                final_question["problem_id"] = f"{msc_code}-{count:03d}"
                print(f"    -> ID: {final_question['problem_id']}")

                statement = final_question.get("statement", "")
                if not statement:
                    print("    -> WARNING: No statement found. Skipping remaining steps for this file.")
                    continue

                # --- Step 3: Generate hints and solution ---
                print("  Step 3: Generating hints and solution...")
                solution_prompt = build_prompt("solution", statement)
                response = model.generate_content(solution_prompt)
                solutions = json.loads(clean_gemini_response(response.text))
                final_question.update(solutions)
                time.sleep(1)

                # --- Step 4: Generate diagram data ---
                print("  Step 4: Generating diagram data...")
                diagram_prompt = build_prompt("diagram", statement)
                response = model.generate_content(diagram_prompt)
                final_question["diagram_data"] = json.loads(clean_gemini_response(response.text))
                time.sleep(1)

                # --- Step 5: Add default fields and append ---
                final_question.setdefault("validation_status", "unverified")
                final_question.setdefault("flags", [])

                all_questions.append(final_question)
                print("  --- File processing complete. ---")

            except Exception as e:
                print(f"  -> FATAL ERROR processing {file_path}: {e}")

    # --- Final Step: Save the complete dataset ---
    with open(FINAL_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, indent=4)

    print(f"\n\n✅✅ Master pipeline finished! Complete dataset saved to '{FINAL_OUTPUT_FILE}' ✅✅")
    return True


def main():
    """
    Main function to run the complete pipeline with mode selection.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Document Processing Pipeline - Parse images and/or organize with Gemini"
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['parse', 'organize', 'both'],
        default='both',
        help='Mode: "parse" (only parse images), "organize" (only run Gemini), "both" (default: run both steps)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("COMBINED DOCUMENT PROCESSING PIPELINE")
    print(f"Mode: {args.mode.upper()}")
    print("=" * 60)

    # Step 1: Parse documents (if mode is 'parse' or 'both')
    if args.mode in ['parse', 'both']:
        if not INPUT_IMAGES_DIR.is_dir():
            print(f"\nError: The directory '{INPUT_IMAGES_DIR}' does not exist.")
            print("Please create it and add your image files.")
            return

        if not parse_documents():
            print("\n❌ Document parsing failed. Pipeline stopped.")
            return

    # Step 2: Run master pipeline (if mode is 'organize' or 'both')
    if args.mode in ['organize', 'both']:
        if not PARSED_DOCUMENTS_DIR.is_dir() or not any(PARSED_DOCUMENTS_DIR.glob("*.json")):
            print(f"\nError: No parsed documents found in '{PARSED_DOCUMENTS_DIR}'")
            print("Run with --mode parse first to generate parsed documents.")
            return

        if not run_master_pipeline():
            print("\n❌ Master pipeline failed.")
            return

    print("\n" + "=" * 60)
    print("🎉 PIPELINE COMPLETED SUCCESSFULLY! 🎉")
    print("=" * 60)


if __name__ == "__main__":
    main()