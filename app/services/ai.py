import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError


load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY was not found in .env")


client = genai.Client(api_key=GEMINI_API_KEY)


class AIReviewResult:
    recommendation: str
    confidence: float
    analysis: str


def call_gemini(prompt: str):
    delays = [1, 2, 4]

    for attempt, delay in enumerate(delays, start=1):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "recommendation": {
                                "type": "string",
                                "enum": [
                                    "APPROVE",
                                    "REJECT",
                                    "NEEDS_REVIEW"
                                ]
                            },
                            "confidence": {
                                "type": "number"
                            },
                            "analysis": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "recommendation",
                            "confidence",
                            "analysis"
                        ]
                    }
                )
            )

            if response.parsed:
                return response.parsed

            raise ValueError("Gemini returned no structured response")

        except ServerError as error:
            if error.code == 503:
                print(
                    f"Gemini unavailable. "
                    f"Attempt {attempt}/{len(delays)}"
                )

                if attempt < len(delays):
                    time.sleep(delay)
                    continue

                return {
                    "recommendation": "NEEDS_REVIEW",
                    "confidence": 0.0,
                    "analysis": (
                        "AI review is temporarily unavailable. "
                        "Manual review is required."
                    )
                }

            raise


def review_submission(
    condition: str,
    submission_description: str,
    file_url: str | None = None
):
    prompt = f"""
You are PalPay AI.

Your role is to evaluate evidence for a conditional payment.

You MUST NOT:
- authorize a payment
- execute a payment
- claim that you opened a URL
- assume evidence that was not provided

Your task is only to determine whether the submitted evidence
appears to satisfy the payment condition.

PAYMENT CONDITION:
{condition}

SUBMISSION DESCRIPTION:
{submission_description}

REFERENCE URL:
{file_url or "No URL provided"}

DECISION RULES:

APPROVE:
Use this only when the submitted evidence clearly satisfies
the payment condition.

REJECT:
Use this when the submission clearly shows that the required
condition has not been completed.

NEEDS_REVIEW:
Use this when:
- the evidence is incomplete
- the evidence is ambiguous
- the condition cannot be verified
- more information is required
- the URL would need to be inspected before making a decision

The confidence value must be between 0 and 1.

Keep the analysis concise and explain why you chose the recommendation.
"""

    result = call_gemini(prompt)

    recommendation = result["recommendation"]
    confidence = float(result["confidence"])
    analysis = result["analysis"]

    allowed_recommendations = {
        "APPROVE",
        "REJECT",
        "NEEDS_REVIEW"
    }

    if recommendation not in allowed_recommendations:
        return {
            "recommendation": "NEEDS_REVIEW",
            "confidence": 0.0,
            "analysis": (
                "AI returned an invalid recommendation. "
                "Manual review is required."
            )
        }

    if not 0 <= confidence <= 1:
        return {
            "recommendation": "NEEDS_REVIEW",
            "confidence": 0.0,
            "analysis": (
                "AI returned an invalid confidence score. "
                "Manual review is required."
            )
        }

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "analysis": analysis
    }