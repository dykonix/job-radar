"""Evidence-grounded OpenAI resume-to-job assessment."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

ASSESSMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fit_score": {"type": "integer"},
        "decision": {"type": "string", "enum": ["APPLY", "APPLY WITH CAUTION", "DO NOT APPLY"]},
        "summary": {"type": "string"},
        "rationale": {"type": "string"},
        "strong_evidence": {"type": "array", "items": {"type": "string"}},
        "requirement_matches": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "requirement": {"type": "string"},
                    "classification": {"type": "string", "enum": ["STRONG MATCH", "PARTIAL MATCH", "TRANSFERABLE", "GAP", "UNKNOWN"]},
                    "evidence": {"type": "string"}
                },
                "required": ["requirement", "classification", "evidence"]
            }
        },
        "screening_risks": {"type": "array", "items": {"type": "string"}},
        "covered_keywords": {"type": "array", "items": {"type": "string"}},
        "missing_keywords": {"type": "array", "items": {"type": "string"}},
        "safe_to_add": {"type": "array", "items": {"type": "string"}},
        "do_not_add": {"type": "array", "items": {"type": "string"}},
        "tailoring_actions": {"type": "array", "items": {"type": "string"}}
    },
    "required": [
        "fit_score", "decision", "summary", "rationale", "strong_evidence",
        "requirement_matches", "screening_risks", "covered_keywords",
        "missing_keywords", "safe_to_add", "do_not_add", "tailoring_actions"
    ]
}


def extract_resume_text(file_path: str) -> str:
    """Extract text locally; resume bytes are not uploaded as files."""
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Resume file not found: {path.name}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        pages = PdfReader(str(path)).pages
        text = "\n".join(page.extract_text() or "" for page in pages)
    elif suffix == ".docx":
        from docx import Document
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        for table in doc.tables:
            for row in table.rows:
                text += "\n" + " | ".join(cell.text for cell in row.cells)
    else:
        raise ValueError("Unsupported resume format. Upload PDF or DOCX.")
    text = text.strip()
    if len(text) < 150:
        raise ValueError("Could not extract enough text from this resume. It may be scanned/image-only; use a text-based PDF or DOCX.")
    return text[:30000]


def assess_resume(job: dict[str, Any], resume: dict[str, Any], model: str | None = None) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing. Add it to your local .env file and restart Job Radar.")
    if not job.get("job_description", "").strip():
        raise ValueError("This vacancy has no job description. Add the full JD before assessing.")
    if not resume.get("file_path"):
        raise ValueError(f"No resume file is registered for {resume.get('name', 'this profile')}. Upload it under Resume Profiles.")
    resume_text = extract_resume_text(str(resume["file_path"]))
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    chosen_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    system_prompt = (
        "You are a rigorous hiring manager and ATS analyst. Compare the job only with the supplied resume text "
        "and verified evidence notes. Never invent experience, tools, metrics, certifications, industries, "
        "seniority or responsibilities. Do not treat a keyword as proof. Classify every material requirement "
        "as STRONG MATCH, PARTIAL MATCH, TRANSFERABLE, GAP or UNKNOWN. TRANSFERABLE means adjacent evidence, "
        "not direct experience. Use UNKNOWN when evidence is insufficient. A mandatory location, work "
        "authorisation, education, certification or years-of-experience requirement that is unmet or unclear "
        "must materially affect the decision. Do not assume India eligibility from the word remote. "
        "Recommend APPLY only when evidence supports a credible shortlist case and no decisive mandatory gap "
        "is apparent; otherwise use APPLY WITH CAUTION or DO NOT APPLY. Fit score is an evidence-based "
        "heuristic, not an ATS probability. For missing keywords, separate genuinely safe additions from "
        "unsupported claims. If source text is ambiguous, state that. Return only the required structured result."
    )
    user_payload = {
        "job": {
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "work_mode": job.get("work_mode"),
            "employment_type": job.get("employment_type"),
            "compensation": job.get("compensation"),
            "eligibility_status": job.get("eligibility_status"),
            "eligibility_reason": job.get("eligibility_reason"),
            "job_description": job.get("job_description")
        },
        "resume_profile": {
            "name": resume.get("name"),
            "resume_type": resume.get("resume_type"),
            "version_label": resume.get("version_label"),
            "verified_evidence_notes": resume.get("evidence_notes") or "",
            "resume_text": resume_text
        },
        "instructions": [
            "Assess this resume independently; do not infer facts from the other resume profile.",
            "List the most important requirements, including seniority, domain, tools, methodology, education and mandatory filters.",
            "Cite concise resume evidence for each match. If evidence is absent, say so.",
            "Do not recommend adding a keyword unless the resume text or verified notes substantiate it.",
            "Include a brief ATS keyword audit and specific changes to make before applying.",
            "A job's India eligibility remains unverified unless the supplied job data explicitly confirms it."
        ]
    }
    response = client.responses.create(
        model=chosen_model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "job_fit_assessment",
                "strict": True,
                "schema": ASSESSMENT_SCHEMA
            }
        },
        max_output_tokens=5000
    )
    if not response.output_text:
        raise ValueError("OpenAI returned no assessment text. Try again or select a different model.")
    result = json.loads(response.output_text)
    score = int(result["fit_score"])
    if score < 0 or score > 100:
        raise ValueError("The model returned an invalid fit score.")
    return result
