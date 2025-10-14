This is the strucure of a single question, represented as a document in the database. All the questions i.e documents together form the collection.
```json
{
  "problem_id": "<unique_identifier>",
  "question_type": "<question_type>",
  "source": {
    "type": "generated"
  },
  "subfield": ["<MSC_code>"],
  "topic": ["<topic_code>"],
  "gradelevel": ["<level1>", "<level2>"],
  "statement": "<problem_statement>",
  "diagram_data": {
    "type": "<diagram_type>",
    "objects": [
      #geometric or Venn diagram objects with properties
    ],
    "labels": ["<label1>", "<label2>"],
    "universal_set": "<total_if_applicable>",
    "image_path": "<relative_path_of_image>"
  },
  "hints": ["<hint1>", "<hint2>"],
  "solution": "<solution_text_or_formula>",
  "validation_status": "unverified",
  "flags": [
    { "type": "<issue_type>", "details": "<description>" }
  ]
}
```

