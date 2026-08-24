import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def extract_medical_information(image_bytes: bytes, mime_type: str):

    prompt = """
You are a medical document OCR and information extraction assistant.

Analyze the uploaded image.

Extract the information that is clearly visible in the document.

Return ONLY valid JSON.

Do not invent or guess information.

If something is not present, use null or an empty array.

Extract:

1. raw_text
2. summary
3. medications
4. diagnoses
5. symptoms
6. doctor
7. date
8. tests
9. recommendations

For medications, use:

{
  "name": "...",
  "dosage": "...",
  "frequency": "...",
  "duration": "..."
}

If handwriting is unclear, mark the value as "unclear" rather than guessing.

JSON format:

{
  "raw_text": "...",
  "summary": "...",
  "medications": [],
  "diagnoses": [],
  "symptoms": [],
  "doctor": null,
  "date": null,
  "tests": [],
  "recommendations": []
}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            ),
            prompt
        ]
    )

    text = response.text

    # Remove markdown code fences if Gemini returns them
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    return json.loads(text)