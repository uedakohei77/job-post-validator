import json
import os
import sys
from google import genai
from google.genai import types
from google.genai.errors import APIError
from config import settings
from src.models import VolunteerPostValidation

def load_historical_examples():
    """
    Loads few-shot historical validation examples from the configured JSON file.
    """
    path = settings.HISTORICAL_POSTS_PATH
    if not os.path.exists(path):
        print(f"Warning: Historical posts file not found at {path}. Proceeding without few-shot examples.")
        return []
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: Failed to read historical posts from {path}: {e}")
        return []


def build_validation_prompt(post_text, examples):
    """
    Constructs the prompt containing business rules and few-shot examples.
    """
    # Format the few-shot examples dynamically
    formatted_examples = ""
    for idx, ex in enumerate(examples, 1):
        formatted_examples += f"""
Example {idx}:
[INPUT POST]
{ex['text']}

[EXPECTED OUTPUT SCHEMA MATCH]
{{
  "is_valid": {str(ex['is_valid']).lower()},
  "extracted_duration_hours": {ex['extracted_duration_hours']},
  "extracted_points": {ex['extracted_points']},
  "assigned_points_per_hour": {ex['assigned_points_per_hour']},
  "category": "{ex['category']}",
  "reasoning": "{ex['reasoning']}",
  "corrections_needed": {json.dumps(ex['corrections_needed'])}
}}
-----------------------------------------
"""

    prompt = f"""You are an expert system designed to validate volunteer job postings.
Your task is to analyze the text of a volunteer posting and verify if the reward points offered match the scope and nature of the work.

### Business Rules for Point Allocation:
1. **Time & Duration Extraction:**
   - Extract the `start_time` and `end_time` (or total duration if explicitly stated) and calculate the total duration in hours.
   
2. **The Baseline Rule:**
   - Standard volunteer work (e.g., desk jobs, admin help, basic hosting) is calculated at **1 point per working hour**.

3. **The Complexity Flex:**
   - You have flexibility to accept deviations from the baseline rule if the text describes high-effort, high-skill, or physically demanding work (e.g., heavy manual labor, moving furniture up stairs). Higher points per hour (e.g., 2.0 to 3.0 points/hour) are acceptable and valid for these postings.

4. **The "Passive/Storage" Exception:**
   - Some volunteer postings involve providing space rather than active labor (e.g., storing boxes in a garage, hosting equipment). In these passive, long-term cases, the total points offered must be **low (e.g., only 2 or 3 points total)**, despite a long calendar duration. High total points for passive storage must be flagged as invalid.

5. **Flagging Threshold:**
   - Do not flag postings for minor deviations. Only set `is_valid` to false if the reward points are completely unreasonable or "far away" from the baseline rules, exceptions, or historical precedents.
   - If a post is invalid, state the required corrections in `corrections_needed`. If valid, `corrections_needed` must be an empty list.

### Historical Reference Examples:
{formatted_examples}

### Validate the following Volunteer Post:
[INPUT POST]
{post_text}

Provide the validation report matching the required schema.
"""
    return prompt


def validate_volunteer_post(post_text):
    """
    Validates a single volunteer job posting using Gemini and structured outputs.
    
    Args:
        post_text (str): The text of the volunteer posting.
        
    Returns:
        VolunteerPostValidation: The Pydantic validation report.
    """
    # Ensure Gemini API key is configured
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("Error: GEMINI_API_KEY is not set. Please configure it in your environment or .env file.")
        sys.exit(1)
        
    # Initialize the official Google GenAI Client
    client = genai.Client(api_key=api_key)
    
    # Load examples for few-shot learning
    examples = load_historical_examples()
    
    # Build prompt
    prompt = build_validation_prompt(post_text, examples)
    
    try:
        # Call Gemini using Structured Outputs via Pydantic schema
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VolunteerPostValidation,
                temperature=0.1,  # Low temperature for deterministic analysis
            ),
        )
        
        # Parse the JSON response into the Pydantic model
        validation_report = VolunteerPostValidation.model_validate_json(response.text)
        return validation_report
        
    except APIError as e:
        print(f"Gemini API Error occurred: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred during validation: {e}")
        raise
