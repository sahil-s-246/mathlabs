This is the strucure of a single question, represented as a document in the database. All the questions i.e documents together form the collection.
```json
{
  "schema_version": "mcq-1.0",
  "problem_id": "XX-YYY",
  "question_type": "multiple_choice", 
  "source": {
    "type": "extract|generation",
    "book_title": "Title_of_the_Book",
    "authors": ["Author_1_Name", "Author_2_Name", "..."],
    "edition": 1,
    "chapter": 1,
    "page": 111
  },
  "subfield": ["XX"],
  "topic": [
	  "topic_1",
    "topic_2",
    "..."
    ],
  "gradelevel": ["College-level|High-school-level|Graduate-level|Above-graduate"],
  "statement": "Statement-of-the-prompt, make sure to use $...$ or $$...$$ to wrap around $$\\LaTeX$$ expressions.",
  "diagram_data": {
    "type": "formula|image|table|...",
    "image_path": "images/XX-YYY.png"
  },

  "choices": [
    { "id": "A", 
	    "text": "Choice_A_text"
	  },
    { "id": "B", 
	    "text": "$Choice_B_text$" 
	  },
    { "id": "C", 
	    "text": "$Choice_C_text$" 
	  },
    { "id": "D", 
	    "text": "$Choice_D_text$" 
	  }
  ],

  "answer": {
    "correct_ids": ["A"],                  
    "explanation": "Explanation-of-the-answer, make sure to use $...$ or $$...$$ to wrap around $$\\LaTeX$$ expressions.",
    "distractor_rationales": {             // optional: discussion why the distractors are wrong
      "B": "Explanation to why B is wrong.",
      "C": "Explanation to why C is wrong.",
      "D": "Explanation to why D is wrong."
    },
  },

  "evaluation": {
    "scoring": { "type": "all_or_nothing", "points": 1 },
    "allow_partial_credit": false|true          // may be true for MCQs allowing more than one answers
  },

  "randomization": {
    "shuffle_choices": true|false,               // whether or not some choicees should be shuffled
    "lock_ids": [],                        // questions that require to be locked in place
    "group_shuffle": []                    // question ids that should be shuffled together (that they are similar)
  "hints": 
  [
		"No.1 Hint",
		"No.2 Hint",
		"..."
   ],
  "difficulty": "hard|medium|easy",
  "bloom_taxonomy": ["Create", "Evaluate", "Analyze", "Apply", "Comprehend", "Remember"] // due to the nature of MCQs, the Create type is going to be very hard to achieve
  "validation_status": "unverified",
  "flags": []
}

```

