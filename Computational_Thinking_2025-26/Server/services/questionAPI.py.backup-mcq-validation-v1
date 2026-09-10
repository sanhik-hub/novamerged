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
from services.supabase_service import create_signedURL

load_dotenv()
api_key1 = os.getenv("API_KEY1")
api_key2 = os.getenv("API_KEY2")

prompt = """
You are an AI Computational Thinking Mathematics Tutor.

The user provides a mathematics problem as text, an image, or both. Analyze the complete problem, including any diagrams/images. Do not invent missing or unreadable information.

First, determine whether the input is a valid mathematics problem. If it is not, cannot be understood reliably, or is unrelated to the selected chapter, set "is_relevant" to false and provide a concise, friendly error_message. Otherwise set it to true and continue.

For a relevant problem:

1. ORIGINAL/BOSS QUESTION
Generate 4 multiple-choice options with exactly one correct answer. Also provide:
- the original question
- correct option
- a basic hint
- a detailed hint
- a complete step-by-step solution

2. COMPUTATIONAL THINKING BREAKDOWN
Break the original problem into 5–15 smaller multiple-choice questions that progressively build the knowledge and intermediate results required to solve the original problem.

Use Computational Thinking naturally:
- Decomposition: divide the problem into smaller tasks.
- Pattern recognition: identify useful mathematical patterns or relationships.
- Abstraction: focus on relevant information.
- Algorithmic thinking: determine the correct sequence of operations.

The smaller questions must form a logical progression and directly help the student solve the original problem.

For every smaller question:
- Provide exactly 4 options with exactly one correct answer.
- Include the question text.
- Include the correct option.
- Give a basic hint.
- Give a concise solution.
- Make incorrect options plausible mistakes.
- Randomize the correct option position.
- Include intermediate results needed by later questions.

The student should have enough knowledge and intermediate results after completing the smaller questions to solve the original problem independently.

Do not reveal answers unnecessarily through hints. Hints should guide reasoning rather than directly give the answer.

Match the difficulty and mathematical level of the original problem. The AI response must contain proper mathematical symbols like √(sqrt), π(pi), exponents(²) etc and do not use unicode characters.

Return ONLY valid JSON and follow the exact JSON structure/schema configured for this request. Do not add, remove, rename, or restructure fields. Do not include Markdown, code fences, explanations, or text outside the JSON.

Before returning, verify:
- The original problem was interpreted correctly.
- All mathematics is correct.
- There are 5–15 smaller questions.
- Every question has exactly 4 options and one correct answer.
- Hints, answers, and solutions are consistent.
- The smaller questions collectively prepare the student to solve the original problem.
- The output follows the configured JSON schema exactly.
"""


prompt2="""  
You are a patient AI Computational Thinking Mathematics Tutor.

The student answered one question incorrectly. Your goal is to help the student understand the concept without immediately revealing the final answer.

Generate 3 to 5 small multiple-choice questions that guide the student from the required basic concept toward understanding the incorrect question.The question should not match with the questions in the questionJson and should not be repeated,you need to provide different questions for the user to understand.

Requirements:
- Questions must focus only on the concept needed for the incorrect question.
- Arrange the questions from easiest to hardest.
- Each question must have exactly 4 options.
- Each question must have exactly one correct option.
- Make incorrect options plausible mathematical mistakes.
- Include a short hint that does not directly reveal the answer.
- Include the correct option number.
- Do not directly solve the original problem.
- Do not mention that the student is stupid or criticize the student.
- Use clear and encouraging language.
- Return only valid JSON.

"""



response_schema1 = {
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
                        }
                    },
                    "required": [
                        "question",
                        "options",
                        "hint",
                        "correct_option"
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
                    }
                },
                "required": [
                    "question",
                    "options",
                    "hint",
                    "correct_option"
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


response_schema2 = {
    "type": "object",
    "properties": {
        "ai_questions": {
            "type": "array",
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
                    
                },
                "required": [
                    "question",
                    "options",
                    "hint",
                    "correct_option",
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

            },
            "required": [
                "question",
                "options",
                "hint",
                "correct_option",
            ]
        }
    },
    "required": [
        "ai_questions",
        "user_question"
    ]
}



    

def call_gemini_with_fallback(prompt: str, img_url: str, response_schema: dict):

    models = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite"
    ]

    contents = [prompt]

    if img_url:
        try:
            with urlopen(img_url, timeout=15) as image_response:
                image_data = image_response.read()
                mime_type = image_response.headers.get_content_type()

            if mime_type == "application/octet-stream":
                mime_type = mimetypes.guess_type(
                    urlparse(img_url).path
                )[0]

            supported_mime_types = {
                "image/jpeg",
                "image/jpg",
                "image/png",
                "image/webp",
                "image/heic",
                "image/heif",
            }

            if mime_type not in supported_mime_types:
                raise ValueError(
                    f"Unsupported image MIME type: {mime_type}"
                )

            contents.append(
                types.Part.from_bytes(
                    data=image_data,
                    mime_type=mime_type,
                )
            )

        except Exception as error:
            raise RuntimeError(
                f"Failed to download/process image: {error}"
            )

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


def get_response(username, question, img_path):
    
    if img_path:
        try:
            img_url = create_signedURL(img_path)
        except Exception as e:
            print(f"Error creating signed URL for image {img_path}: {e}")
            img_url = None
    else:
        img_url = None
        
    prompt_with_question = f"{prompt}\n\nUser's question: {question}"
    
    try:
        response = call_gemini_with_fallback(prompt_with_question, img_url, response_schema1)
    
    except Exception as e:
        raise RuntimeError(f"Failed to get response from Gemini API: {e}")
        
    
    return response


def get_Doubtresponse(username, WrongAnsweredquestion, QuestionJson):
    
    img_url = None  # No image for doubt questions
        
    prompt_with_question = f"{prompt2}\n\n {WrongAnsweredquestion}\n\nQuestion Array: {QuestionJson}" 
    
    try:
        response = call_gemini_with_fallback(prompt_with_question, img_url, response_schema2)
    
    except Exception as e:
        raise RuntimeError(f"Failed to get response from Gemini API: {e}")
        
    
    return response









