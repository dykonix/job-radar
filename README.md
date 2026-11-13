# Job Radar — Job Search Command Center

A local-first application for managing the full job-search lifecycle. The database is the system of record; dashboards and AI workflows sit on top of it.

## Current release: 0.3 verification and fit-review foundation

Implemented:
- Manual job intake with original JD, source URL, location, work mode, employment type, compensation, posting date and evidence.
- Persistent SQLite database with relational records for jobs, resumes, assessments, applications, interactions, interviews, outcomes and improvement experiments.
- Two benchmark resume profiles: Project Management and Product Management (covering APM, Product Operations and Product Delivery).
- Application tracking, recruiter activity, interview rounds and outcomes.
- Basic pipeline and funnel counts.
- Target role families include Project Manager, Technical Project Manager, Program/Delivery Manager and Scrum Master.
- India-only working-location policy with CONFIRMED / REVIEW / EXCLUDED eligibility states.
- Manual sync from public Himalayas, Remote OK, We Work Remotely RSS and Remotive feeds; imported jobs retain source attribution and original application URL.
- Source identity deduplication and additive SQLite migrations that preserve existing local records.
- Vacancy verification workflow: India eligibility, open/closed status, evidence text, evidence URL and verification timestamp.
- OpenAI-powered dual-resume assessment using the Responses API and Structured Outputs; each benchmark resume is assessed independently, then compared.
- Requirement classifications: STRONG MATCH / PARTIAL MATCH / TRANSFERABLE / GAP / UNKNOWN; ATS covered/missing/safe-to-add/do-not-add audit; screening risks and tailoring actions.
- PDF/DOCX text extraction runs locally. Extracted resume text, verified evidence notes and the selected job description are sent to OpenAI only when the user explicitly runs an assessment. Results are saved in SQLite as `openai-v1` assessments.
- Resume Profiles page to register local PDF/DOCX versions, version labels and verified evidence notes. Resume files stay under the local data/resumes folder and are not committed to GitHub.
- Freshness buckets are recorded from source publication timestamps; missing timestamps remain unverified.

Not implemented yet:
- Automatic external verification of job eligibility, vacancy status or employer claims; the AI assessment treats these as separate human-verification gates.
- Resume file parsing/version generation.
- LinkedIn, Naukri and Indeed automated connectors (login-gated/restricted access; use alerts or user-submitted URLs unless permitted integration is available).
- Scheduled/background syncing (current discovery is user-triggered from the Streamlit page).
- Automated verification that an employer will hire/payroll in India; the app now records a human evidence-based verification decision.
- AI output is advisory, not a hiring probability or guaranteed ATS result; a human must review evidence, mandatory filters and the final application decision.
- Automated job description parsing into detailed requirements; current feed connector stores the source description and basic metadata.
- Email/LinkedIn integrations or automatic follow-up.
- Cloud deployment, authentication and multi-device sync.

The app deliberately does not fabricate assessments or claim automated discovery.

## Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env (never commit this file)
streamlit run app.py
```

Open the local URL printed by Streamlit (usually http://localhost:8501).

## Data location

SQLite database: `data/job_radar.db`

This database is local and should be backed up. It is excluded from Git. Do not commit personal resumes, API keys, application records or recruiter contact data.

## Architecture

- Streamlit: user interface
- Python: business logic
- SQLite: initial relational persistence
- AWS Strands Agents SDK: planned AI orchestration layer, not yet integrated
- PostgreSQL: possible future migration when multi-user/cloud deployment is needed

## Next development increments

1. Add automatic resume parsing and structured claim extraction (manual local file/version registry is now available).
2. Build structured JD extraction and requirement taxonomy.
3. Implement evidence-grounded comparison against both resumes with explicit STRONG MATCH / PARTIAL MATCH / TRANSFERABLE / GAP / UNKNOWN classifications.
4. Add an auditable decision rubric and ATS keyword analysis.
5. Add resume tailoring/version history with source-to-claim traceability.
6. Add permitted-source job discovery and posting-date verification.
7. Add outcome analytics and an AI learning/recommendation workflow.


## Run the database tests

```bash
python -m unittest discover -s tests -v
```

A GitHub Actions workflow runs these checks on pushes and pull requests to `main`.


## OpenAI assessment setup

1. Copy `.env.example` to `.env` in the project root.
2. Set `OPENAI_API_KEY` to your API key. Optionally set `OPENAI_MODEL` (default: `gpt-4o-mini`).
3. Install updated dependencies with `pip install -r requirements.txt` and restart Streamlit.
4. Register both PDF/DOCX benchmark resumes under **Resume Profiles**.
5. Open a vacancy under **Review & Fit** and select **Run OpenAI assessment against both resumes**.

The app extracts PDF/DOCX text locally. When the assessment button is pressed, extracted resume text, verified evidence notes and the selected job description are transmitted to OpenAI for processing. API usage is billed to the configured OpenAI API account. Keep `.env`, `data/`, and personal resume files local; never commit API keys or personal files. Scanned/image-only PDFs may not yield extractable text and should be replaced with text-based PDFs or DOCX files.
