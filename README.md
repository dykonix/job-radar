# Job Radar — Job Search Command Center

A local-first application for managing the full job-search lifecycle. The database is the system of record; dashboards and AI workflows sit on top of it.

## Current release: 0.1 foundation

Implemented:
- Manual job intake with original JD, source URL, location, work mode, employment type, compensation, posting date and evidence.
- Persistent SQLite database with relational records for jobs, resumes, assessments, applications, interactions, interviews, outcomes and improvement experiments.
- Comparison record for both primary resumes (Project Manager and Associate Product Manager).
- Application tracking, recruiter activity, interview rounds and outcomes.
- Basic pipeline and funnel counts.
- Freshness classification fields for India 24-hour and international remote 72-hour queues.

Not implemented yet:
- AI-based JD extraction and fit assessment.
- Resume file parsing/version generation.
- Automated job discovery or job-board integrations.
- Email/LinkedIn integrations or automatic follow-up.
- Cloud deployment, authentication and multi-device sync.

The app deliberately does not fabricate assessments or claim automated discovery.

## Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

1. Add resume file upload, parsing and version registry.
2. Build structured JD extraction and requirement taxonomy.
3. Implement evidence-grounded comparison against both resumes with explicit STRONG MATCH / PARTIAL MATCH / TRANSFERABLE / GAP / UNKNOWN classifications.
4. Add an auditable decision rubric and ATS keyword analysis.
5. Add resume tailoring/version history with source-to-claim traceability.
6. Add permitted-source job discovery and posting-date verification.
7. Add outcome analytics and an AI learning/recommendation workflow.
