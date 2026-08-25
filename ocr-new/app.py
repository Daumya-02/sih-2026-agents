import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from datetime import date

from ocr_agent import extract_medical_information
from backend_client import get_logs, update_log
from ratelimit import enforce_rate_limit


app = FastAPI(
    title="Medical OCR Agent"
)

# /ocr has no user_id (it doesn't touch the backend), so it's rate-limited by
# client IP instead; /ocr-and-log is keyed by user_id like the other agents.
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))


@app.get("/")
def root():
    return {
        "message": "Medical OCR Agent is running"
    }


@app.post("/ocr")
async def process_document(
    request: Request,
    file: UploadFile = File(...)
):
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(client_ip, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_SECONDS)
    try:
        image_bytes = await file.read()

        result = extract_medical_information(
            image_bytes,
            file.content_type
        )

        return {
            "success": True,
            "extracted": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/ocr-and-log")
async def process_document_and_log(
    user_id: int = Form(...),
    file: UploadFile = File(...),
    log_date: str = Form(None)
):
    enforce_rate_limit(str(user_id), RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_SECONDS)
    try:

        # --------------------------------
        # 1. Determine date
        # --------------------------------

        if not log_date:
            log_date = date.today().isoformat()


        # --------------------------------
        # 2. Read image
        # --------------------------------

        image_bytes = await file.read()


        # --------------------------------
        # 3. Run OCR + medical extraction
        # --------------------------------

        extracted = extract_medical_information(
            image_bytes,
            file.content_type
        )


        # --------------------------------
        # 4. Get existing user logs
        # --------------------------------

        logs_response = get_logs(user_id)

        logs = logs_response.get("logs", [])


        # Find today's log
        existing_log = None

        for log in logs:
            if log.get("date") == log_date:
                existing_log = log
                break


        # --------------------------------
        # 5. Get existing data
        # --------------------------------

        if existing_log:

            existing_symptoms = existing_log.get(
                "symptoms", []
            )

            existing_note = existing_log.get(
                "note"
            ) or ""

        else:

            existing_symptoms = []
            existing_note = ""


        # --------------------------------
        # 6. Merge symptoms
        # --------------------------------

        new_symptoms = extracted.get(
            "symptoms", []
        )

        merged_symptoms = list(
            dict.fromkeys(
                existing_symptoms + new_symptoms
            )
        )


        # --------------------------------
        # 7. Create medication text
        # --------------------------------

        medications = extracted.get(
            "medications", []
        )

        medication_lines = []

        for medication in medications:

            name = medication.get(
                "name", "Unknown"
            )

            dosage = medication.get(
                "dosage"
            )

            frequency = medication.get(
                "frequency"
            )

            duration = medication.get(
                "duration"
            )

            parts = [name]

            if dosage:
                parts.append(dosage)

            if frequency:
                parts.append(frequency)

            if duration:
                parts.append(duration)

            medication_lines.append(
                " - ".join(parts)
            )


        # --------------------------------
        # 8. Build note
        # --------------------------------

        new_note_parts = []

        if extracted.get("summary"):
            new_note_parts.append(
                f"Medical document summary: "
                f"{extracted['summary']}"
            )

        if medication_lines:
            new_note_parts.append(
                "Medications: "
                + "; ".join(medication_lines)
            )

        diagnoses = extracted.get(
            "diagnoses", []
        )

        if diagnoses:
            new_note_parts.append(
                "Diagnoses: "
                + ", ".join(diagnoses)
            )

        recommendations = extracted.get(
            "recommendations", []
        )

        if recommendations:
            new_note_parts.append(
                "Recommendations: "
                + ", ".join(recommendations)
            )


        new_note = "\n".join(
            new_note_parts
        )


        # --------------------------------
        # 9. Merge with existing note
        # --------------------------------

        if existing_note and new_note:

            final_note = (
                existing_note
                + "\n\n"
                + new_note
            )

        else:

            final_note = (
                new_note
                or existing_note
                or None
            )


        # --------------------------------
        # 10. Update backend
        # --------------------------------

        log_data = {
            "symptoms": merged_symptoms,
            "note": final_note
        }

        backend_result = update_log(
            user_id,
            log_date,
            log_data
        )


        # --------------------------------
        # 11. Return result
        # --------------------------------

        return {
            "success": True,
            "user_id": user_id,
            "date": log_date,
            "extracted": extracted,
            "updated_log": backend_result
        }


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )