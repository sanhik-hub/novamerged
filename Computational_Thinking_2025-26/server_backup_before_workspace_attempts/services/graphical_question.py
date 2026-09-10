import os
import json
import mimetypes
from urllib.parse import urlparse
from urllib.request import urlopen

from google import genai
from google.genai import types
from database.db import db
from database.models import User
from dotenv import load_dotenv  

load_dotenv()
api_key1 = os.getenv("API_KEY1")
api_key2 = os.getenv("API_KEY2")

prompt = """
You are an AI Computational Thinking Mathematics Tutor.

The user provides a mathematics problem as text and may optionally provide a graph or graph coordinates. Analyze the complete problem and any provided graph.

First determine whether the input is:

1. A valid mathematics problem.
2. Related to the selected chapter.
3. Solvable graphically.

A problem is graphically solvable if it can be represented and solved using a 2D Cartesian graph. A graph or coordinates do NOT need to be provided. For example:

x + 2y = 20
2x + y = 25

is graphically solvable because both equations represent straight lines that can be plotted and their intersection can be found.

If the problem is a valid maths problem but cannot be solved graphically, set "is_relevant" to false and use exactly:
"This question cannot be solved graphically please switch to Standard Mode"

If invalid, unclear, or unrelated to the selected chapter, set "is_relevant" to false and provide a concise, friendly error_message.

Otherwise set "is_relevant" to true and continue.

GRAPH AND COORDINATE RULES:

If coordinates/graph are provided:

* Treat them as the source of truth.
* Never invent, modify, approximate, or contradict them.
* Use only the minimum relevant coordinates for each question.

If no coordinates/graph are provided:

* For graphically solvable problems, calculate the mathematical coordinates, intercepts, intersections, or other values needed to construct the graph.
* Do not reject a problem simply because coordinates were not provided.

For every question:

* coordinates must use [x, y] order.
* Format: [[x1, y1], [x2, y2], ...]
* Include only coordinates relevant to that question.
* Use 1–4 coordinate pairs.
* If more than 4 are needed, restructure the question.

1. ORIGINAL/BOSS QUESTION

Generate:

* Original question.
* Exactly 4 MCQ options with exactly one correct answer.
* Correct option.
* Basic hint.
* Relevant graph coordinates.

2. COMPUTATIONAL THINKING BREAKDOWN

Create 5–15 smaller MCQs that progressively build toward solving the original problem.

Use:

* Decomposition.
* Pattern recognition.
* Abstraction.
* Algorithmic thinking.

For every smaller question provide:

* Question.
* Exactly 4 options with exactly one correct answer.
* Correct option.
* Basic hint.
* Relevant coordinates.

Incorrect options should represent plausible mistakes. Randomize the correct-option position. Include intermediate results needed by later questions.

Hints should guide reasoning without directly revealing the answer.

Use proper mathematical notation such as √, π, ², ³, ≤, ≥, etc. Do not use Unicode escape sequences such as \u00b2.

OUTPUT:

Return ONLY valid JSON using the exact configured schema. Do not add, remove, rename, or restructure fields. Do not include Markdown or text outside the JSON.

FINAL CHECK:

* Correctly classify graphical solvability.
* Do not require a supplied graph/coordinates.
* All mathematics is correct.
* 5–15 smaller questions.
* Every question has exactly 4 options and 1 correct answer.
* Coordinates are relevant, correctly ordered, and contain 1–4 pairs.
* Hints and answers are consistent.
* Smaller questions logically prepare the student for the original.
* Output exactly matches the configured JSON schema.

"""

response_schema = {
        "type": "object",
        "properties": {
            "is_relevant": {
                "type": "boolean"
            },
            "error_message": {
                "type": "string"
            },
            "ai_questions": {
                "type": "array",
                "minItems": 5,
                "maxItems": 15,
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string"
                        },
                        "options": {
                            "type": "array",
                            "minItems": 4,
                            "maxItems": 4,
                            "items": {
                                "type": "string"
                            }
                        },
                        "hint": {
                            "type": "string"
                        },
                        "correct_option": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 4
                        },
                        "coordinates": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 4,
                            "items": {
                                "type": "array",
                                "minItems": 2,
                                "maxItems": 2,
                                "items": {
                                    "type": "number"
                                }
                            }
                        }
                    },
                    "required": [
                        "question",
                        "options",
                        "hint",
                        "correct_option",
                        "coordinates"
                    ]
                }
            },
            "user_question": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string"
                    },
                    "options": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {
                            "type": "string"
                        }
                    },
                    "hint": {
                        "type": "string"
                    },
                    "correct_option": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 4
                    },
                    "coordinates": {
                        "type": "array",
                        "minItems": 0,
                        "maxItems": 4,
                        "items": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 2,
                            "items": {
                                "type": "number"
                            }
                        }
                    }
                },
                "required": [
                    "question",
                    "options",
                    "hint",
                    "correct_option",
                    "coordinates"
                ]
            }
        },
        "required": [
            "is_relevant",
            "error_message",
            "ai_questions",
            "user_question"
        ]
}


def call_gemini_with_fallback(prompt: str, response_schema: dict):

    models = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite"
    ]

    contents = [prompt]


    # ------------------------------------------------
    # Gemini fallback
    # ------------------------------------------------

    for key_index, key in enumerate(
        (api_key1, api_key2),
        start=1
    ):

        client = genai.Client(api_key=key)

        for model in models:

            try:

                print(
                    f"Trying key {key_index}, model {model}"
                )

                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_schema,
                    ),
                )

                if response.parsed is not None:
                    print(
                        f"Success: key {key_index}, model {model}"
                    )
                    print(f"Pahrased response is returned")

                    return response.parsed

                if response.text:
                    print(
                        f"Success: key {key_index}, model {model}"
                    )
                    print(f"Text response is returned:")
                    return json.loads(response.text)

                raise RuntimeError(
                    "Gemini returned an empty response"
                )

            except Exception as error:

                print(
                    f"Failed: key {key_index}, "
                    f"model {model}: "
                    f"{type(error).__name__}: {error}"
                )

                continue

    raise RuntimeError(
        "All Gemini attempts failed"
    )
    
    
    
def get_graphical_response(username, question, coordinates):
        
    prompt_with_question = f"{prompt}\n\nUser's question: {question}\n\nCoordinates:{json.dumps(coordinates)}"
    
    try:
        response = call_gemini_with_fallback(prompt_with_question, response_schema)
    
    except Exception as e:
        raise RuntimeError(f"Failed to get response from Gemini API: {e}")
        
    
    return response
