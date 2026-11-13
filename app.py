from __future__ import annotations

from datetime import date, datetime
import streamlit as st

from src.db import init_db, execute, query_df, query_one
from src.remote_discovery import discover

st.set_page_config(page_title="Job Radar | Job Search Command Center", page_icon="🎯", layout="wide")
init_db()

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1500px;}
div[data-testid="stMetric"] {background: #f7f8fa; padding: 14px 16px; border-radius: 10px;}
.small-muted {color: #667085; font-size: 0.88rem;}
</style>
""", unsafe_allow_html=True)

st.title("🎯 Job Radar")
st.caption("Your job-search operating system · Local database · Evidence-first decisions")

pages = ["Overview", "Discover Remote Jobs", "Review & Fit", "Add a Job", "Job Library", "Assessments", "Applications", "Recruiter Activity", "Interviews & Outcomes", "Learning Log"]
page = st.sidebar.radio("Workspace", pages)
st.sidebar.divider()
st.sidebar.caption("Version 0.3 · Local SQLite")
st.sidebar.caption("Data is stored on this computer in data/job_radar.db")

def fmt_count(sql: str) -> int:
    row = query_one(sql)
    return int(row["n"] if row else 0)



elif page == "Review & Fit":
    st.subheader("Verify vacancy and assess profile fit")
    jobs = query_df("SELECT id,title,company,original_url,location,eligibility_status,vacancy_status FROM jobs ORDER BY discovered_at DESC")
    if jobs.empty:
        st.info("Discover or add a vacancy first.")
    else:
        job_id = st.selectbox("Vacancy to review", jobs.id.tolist(),
            format_func=lambda x: f"#{x} · {jobs.loc[jobs.id==x,'title'].iloc[0]} — {jobs.loc[jobs.id==x,'company'].iloc[0]}")
        job = query_one("SELECT * FROM jobs WHERE id=?", (int(job_id),))
        st.markdown(f"**{job['title']} — {job['company']}**")
        st.write(f"Source: {job['source']} · Location: {job['location'] or 'Not specified'}")
        if job["original_url"]:
            st.markdown(f"[Open original vacancy]({job['original_url']})")
        st.text_area("Imported job description", job["job_description"], height=220, disabled=True)
        st.markdown("### A. Verify vacancy and India eligibility")
        st.caption("Do not mark CONFIRMED merely because a listing says Remote. Check the employer's location restrictions, eligible countries, payroll/contractor rules and application page.")
        with st.form("verify_job_form"):
            eligibility = st.selectbox("Can an India-based candidate work in this role?",
                ["REVIEW", "CONFIRMED", "EXCLUDED"],
                index=["REVIEW","CONFIRMED","EXCLUDED"].index(job["eligibility_status"] or "REVIEW"))
            vacancy = st.selectbox("Vacancy status",
                ["UNVERIFIED", "OPEN", "CLOSED", "EXPIRED", "DUPLICATE"],
                index=["UNVERIFIED","OPEN","CLOSED","EXPIRED","DUPLICATE"].index(job["vacancy_status"] or "UNVERIFIED"))
            evidence = st.text_area("Evidence supporting eligibility/status",
                value=job["eligibility_evidence"] or "", height=100,
                placeholder="Example: Employer careers page says remote within India; contractor hiring in India is accepted.")
            evidence_url = st.text_input("Evidence URL (employer/careers page)", value=job["posted_at_evidence"] or "")
            verify_note = st.text_area("Verification notes", value=job["eligibility_reason"] or "")
            verified = st.form_submit_button("Save verification", type="primary")
            if verified:
                execute("""UPDATE jobs SET eligibility_status=?,vacancy_status=?,eligibility_evidence=?,
                    eligibility_reason=?,posted_at_evidence=?,eligibility_checked_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (eligibility,vacancy,evidence,verify_note,evidence_url,int(job_id)))
                st.success("Verification saved.")
        st.markdown("### B. Record profile-fit assessment")
        st.caption("This release does not yet run an AI assessment. Scores and decisions entered here must be based on the full JD and your verified resume evidence. Do not guess.")
        resumes = query_df("SELECT id,name,resume_type FROM resumes WHERE is_active=1 ORDER BY id")
        for _, resume in resumes.iterrows():
            prior = query_one("SELECT * FROM assessments WHERE job_id=? AND resume_id=? ORDER BY created_at DESC LIMIT 1",
                              (int(job_id),int(resume.id)))
            with st.expander(f"Assess against {resume['name']}", expanded=False):
                with st.form(f"fit_{int(resume.id)}"):
                    score = st.slider("Profile match score (0–100)",0,100,
                        int(prior["fit_score"] or 0) if prior else 0)
                    decision = st.selectbox("Recommendation",
                        ["PENDING","APPLY","APPLY WITH CAUTION","DO NOT APPLY"],
                        index=["PENDING","APPLY","APPLY WITH CAUTION","DO NOT APPLY"].index(prior["decision"]) if prior else 0)
                    strengths = st.text_area("Strong / relevant evidence",value=prior["strengths"] or "" if prior else "")
                    gaps = st.text_area("Partial matches, transferable experience and gaps",value=prior["gaps"] or "" if prior else "")
                    risks = st.text_area("Mandatory screening risks",value=prior["screening_risks"] or "" if prior else "")
                    keywords = st.text_area("ATS: covered / missing / safe to add / do not add",value=prior["ats_keywords"] or "" if prior else "")
                    tailoring = st.text_area("Changes required before applying",value=prior["tailoring_actions"] or "" if prior else "")
                    rationale = st.text_area("Decision rationale",value=prior["rationale"] or "" if prior else "")
                    save_fit = st.form_submit_button("Save fit assessment")
                    if save_fit:
                        execute("""INSERT INTO assessments(job_id,resume_id,decision,fit_score,strengths,gaps,
                            screening_risks,ats_keywords,tailoring_actions,rationale,assessment_version)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id,resume_id,assessment_version) DO UPDATE SET
                            decision=excluded.decision,fit_score=excluded.fit_score,strengths=excluded.strengths,
                            gaps=excluded.gaps,screening_risks=excluded.screening_risks,
                            ats_keywords=excluded.ats_keywords,tailoring_actions=excluded.tailoring_actions,
                            rationale=excluded.rationale,created_at=CURRENT_TIMESTAMP""",
                            (int(job_id),int(resume.id),decision,score,strengths,gaps,risks,keywords,tailoring,rationale,"manual-v1"))
                        st.success("Fit assessment saved.")

if page == "Discover Remote Jobs":
    st.subheader("Discover India-accessible remote PM & Scrum roles")
    st.caption("Fetches public feeds only. A remote label is not proof of India eligibility; ambiguous listings stay in verification.")
    sources = st.multiselect("Sources", ["Himalayas", "Remote OK", "We Work Remotely", "Remotive"],
                             default=["Himalayas", "Remote OK", "We Work Remotely", "Remotive"])
    st.info("Target roles: Technical Project Manager, IT/Software Project Manager, Project Manager, Program/Delivery Manager and Scrum Master. India-only working location; onsite and hybrid roles are not imported.")
    if st.button("Fetch latest remote vacancies", type="primary", disabled=not sources):
        with st.spinner("Fetching public job feeds..."):
            found, errors = discover(sources)
            inserted = 0
            for job in found:
                # A listing is fresh only when its source publication timestamp is available.
                posted = job.get("posted_at")
                freshness = "Unverified"
                if posted:
                    try:
                        from datetime import datetime, timezone
                        dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                        age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600
                        if job["eligibility_status"] == "CONFIRMED" and 0 <= age_hours <= 24:
                            freshness = "India ≤24h"
                        elif 0 <= age_hours <= 72:
                            freshness = "International remote ≤72h"
                        else:
                            freshness = "Outside window"
                    except Exception:
                        pass
                role = "Scrum Master" if "scrum master" in job["title"].lower() else (
                    "Program/Delivery Manager" if any(x in job["title"].lower() for x in ("program manager","delivery manager")) else "Project Manager")
                try:
                    before = query_one("SELECT id FROM jobs WHERE source=? AND source_job_id=?", (job["source"], job["source_job_id"]))
                    if before:
                        execute("""UPDATE jobs SET title=?,company=?,original_url=?,job_description=?,location=?,
                            employment_type=?,posted_at=?,freshness_bucket=?,eligibility_status=?,eligibility_reason=?,
                            source_attribution=?,role_family=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                            (job["title"],job["company"],job["url"],job["description"],job["location"],
                             job["employment_type"],posted,freshness,job["eligibility_status"],job["eligibility_reason"],
                             job["source_attribution"],role,before["id"]))
                    else:
                        execute("""INSERT INTO jobs(title,company,source,original_url,job_description,location,
                            work_mode,employment_type,posted_at,freshness_bucket,source_job_id,source_attribution,
                            role_family,eligibility_status,eligibility_reason)
                            VALUES(?,?,?,?,? ,?,'Remote',?,?,?,?,?,?,?,?)""",
                            (job["title"],job["company"],job["source"],job["url"],job["description"],job["location"],
                             job["employment_type"],posted,freshness,job["source_job_id"],job["source_attribution"],
                             role,job["eligibility_status"],job["eligibility_reason"]))
                        inserted += 1
                except Exception as exc:
                    st.warning(f"Could not save {job.get('title','listing')}: {exc}")
            st.success(f"Fetched {len(found)} listings; {inserted} new records saved.")
            for error in errors:
                st.warning(error)
    st.markdown("### Imported opportunities")
    df = query_df("""SELECT id,title,company,source,role_family,location,posted_at,freshness_bucket,
        eligibility_status,eligibility_reason,vacancy_status,original_url FROM jobs
        WHERE source IN ('Himalayas','Remote OK','We Work Remotely','Remotive')
        ORDER BY discovered_at DESC LIMIT 300""")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption("Himalayas listings must retain visible source credit and use their supplied applicationLink. Other source terms and attribution should be checked before redistributing listings.")
    else:
        st.info("No imported vacancies yet. Select sources and fetch their feeds.")

if page == "Overview":
    st.subheader("Search performance")
    jobs = fmt_count("SELECT COUNT(*) n FROM jobs")
    apps = fmt_count("SELECT COUNT(*) n FROM applications")
    responses = fmt_count("SELECT COUNT(*) n FROM interactions WHERE interaction_type IN ('Recruiter response','Recruiter call','Interview invitation')")
    interviews = fmt_count("SELECT COUNT(*) n FROM interviews")
    offers = fmt_count("SELECT COUNT(*) n FROM outcomes WHERE outcome='Offer'")
    c = st.columns(5)
    for col, label, value in zip(c, ["Jobs saved", "Applications", "Positive responses", "Interview rounds", "Offers"], [jobs, apps, responses, interviews, offers]):
        col.metric(label, value)
    st.markdown("### Current pipeline")
    df = query_df("""SELECT j.title AS Role, j.company AS Company, a.status AS Status,
                     COALESCE(a.applied_at, '—') AS 'Applied on',
                     COALESCE(a.next_follow_up_at, '—') AS 'Next follow-up'
                     FROM applications a JOIN jobs j ON j.id=a.job_id
                     ORDER BY a.updated_at DESC LIMIT 12""")
    if df.empty:
        st.info("No applications recorded yet. Add a job, assess it against both resumes, then record the application.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown("### Funnel")
    funnel = query_df("""SELECT
        (SELECT COUNT(*) FROM applications) AS Applied,
        (SELECT COUNT(DISTINCT application_id) FROM interactions WHERE interaction_type IN ('Recruiter response','Recruiter call','Interview invitation')) AS Responded,
        (SELECT COUNT(DISTINCT application_id) FROM interviews) AS Interviewed,
        (SELECT COUNT(*) FROM outcomes WHERE outcome='Offer') AS Offers""")
    st.dataframe(funnel, use_container_width=True, hide_index=True)
    st.caption("These are descriptive counts. Do not infer causality or stable conversion rates from small samples.")

elif page == "Add a Job":
    st.subheader("Capture a vacancy")
    st.caption("Paste the original job description. Posting-date evidence is stored separately so freshness is verifiable.")
    with st.form("job_intake", clear_on_submit=True):
        col1, col2 = st.columns(2)
        title = col1.text_input("Job title *")
        role_family = col2.selectbox("Target role family", ["Project Manager", "Scrum Master", "Program/Delivery Manager", "Other"])
        company = col2.text_input("Company *")
        source = col1.selectbox("Source", ["LinkedIn", "Naukri", "Indeed", "Company career page", "Referral", "Recruiter", "Other"])
        url = col2.text_input("Original job URL")
        location = col1.text_input("Location")
        eligibility_status = col2.selectbox("India work eligibility", ["REVIEW", "CONFIRMED", "EXCLUDED"])
        work_mode = col2.selectbox("Work mode", ["Unknown", "On-site", "Hybrid", "Remote", "India remote", "International remote"])
        employment = col1.selectbox("Employment type", ["Unknown", "Full-time", "Part-time", "Contract", "Consulting", "Temporary"])
        compensation = col2.text_input("Compensation / range (as published)")
        posted = col1.date_input("Original posting date", value=None)
        posted_evidence = col2.text_input("Posting-date evidence (e.g. employer page timestamp)")
        freshness = col1.selectbox("Freshness queue", ["Unverified", "India ≤24h", "International remote ≤72h", "Approved exception", "Outside window"])
        applicants = col2.text_input("Displayed applicant count (optional)")
        jd = st.text_area("Full job description *", height=260)
        notes = st.text_area("Initial notes", height=90)
        submitted = st.form_submit_button("Save vacancy", type="primary")
        if submitted:
            if not title.strip() or not company.strip() or not jd.strip():
                st.error("Job title, company and full job description are required.")
            else:
                execute("""INSERT INTO jobs(title,company,source,original_url,job_description,location,work_mode,
                    employment_type,compensation,posted_at,posted_at_evidence,freshness_bucket,applicant_count,notes)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (title.strip(), company.strip(), source, url.strip(), jd.strip(), location.strip(), work_mode,
                     employment, compensation.strip(), posted.isoformat() if posted else None,
                     posted_evidence.strip(), freshness, applicants.strip(), notes.strip()))
                execute("UPDATE jobs SET role_family=?, eligibility_status=? WHERE id=(SELECT MAX(id) FROM jobs)", (role_family, eligibility_status))
                st.success("Vacancy saved to the database.")

elif page == "Job Library":
    st.subheader("Job library")
    filters = st.columns(3)
    status_filter = filters[0].selectbox("Status", ["All", "Saved", "Assessing", "Applied", "Archived"])
    freshness_filter = filters[1].selectbox("Freshness", ["All", "Unverified", "India ≤24h", "International remote ≤72h", "Approved exception", "Outside window"])
    search = filters[2].text_input("Search title / company")
    sql = "SELECT id,title,company,source,location,work_mode,employment_type,posted_at,freshness_bucket,status,discovered_at FROM jobs WHERE 1=1"
    params = []
    if status_filter != "All":
        sql += " AND status=?"; params.append(status_filter)
    if freshness_filter != "All":
        sql += " AND freshness_bucket=?"; params.append(freshness_filter)
    if search.strip():
        sql += " AND (title LIKE ? OR company LIKE ?)"; params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY discovered_at DESC"
    df = query_df(sql, tuple(params))
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        selected = st.selectbox("Open job record", df["id"].tolist(), format_func=lambda x: f"#{x} · {df.loc[df.id==x, 'title'].iloc[0]} — {df.loc[df.id==x, 'company'].iloc[0]}")
        job = query_one("SELECT * FROM jobs WHERE id=?", (int(selected),))
        with st.expander("Full job record", expanded=True):
            st.write(f"**{job['title']} — {job['company']}**")
            st.write(job["original_url"] or "No URL supplied")
            st.text_area("Job description", job["job_description"], height=230, disabled=True)
            st.write(f"Posting date: {job['posted_at'] or 'Unknown'} · Evidence: {job['posted_at_evidence'] or 'Not supplied'}")
            new_status = st.selectbox("Update job status", ["Saved", "Assessing", "Applied", "Archived"], index=["Saved","Assessing","Applied","Archived"].index(job["status"]))
            if st.button("Update job status"):
                execute("UPDATE jobs SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, int(selected)))
                st.success("Status updated.")

elif page == "Assessments":
    st.subheader("Compare both resumes against a vacancy")
    jobs = query_df("SELECT id,title,company FROM jobs ORDER BY discovered_at DESC")
    resumes = query_df("SELECT id,name,resume_type FROM resumes WHERE is_active=1 ORDER BY id")
    if jobs.empty:
        st.info("Add a job first.")
    else:
        job_id = st.selectbox("Vacancy", jobs.id.tolist(), format_func=lambda x: f"#{x} · {jobs.loc[jobs.id==x,'title'].iloc[0]} — {jobs.loc[jobs.id==x,'company'].iloc[0]}")
        st.info("This initial build stores structured, evidence-based assessments. AI-generated assessment is not yet connected; do not treat an empty assessment as a fit decision.")
        for _, resume in resumes.iterrows():
            st.markdown(f"#### {resume['name']}")
            prior = query_one("SELECT * FROM assessments WHERE job_id=? AND resume_id=? ORDER BY created_at DESC LIMIT 1", (int(job_id), int(resume.id)))
            with st.form(f"assessment_{resume.id}"):
                decision = st.selectbox("Decision", ["PENDING", "APPLY", "APPLY WITH CAUTION", "DO NOT APPLY"], index=["PENDING","APPLY","APPLY WITH CAUTION","DO NOT APPLY"].index(prior["decision"]) if prior else 0)
                score = st.number_input("Fit score (optional; do not guess)", min_value=0, max_value=100, value=int(prior["fit_score"] or 0) if prior else 0)
                strengths = st.text_area("Evidence / strengths", value=prior["strengths"] or "" if prior else "")
                gaps = st.text_area("Gaps / unknowns", value=prior["gaps"] or "" if prior else "")
                risks = st.text_area("Initial screening risks", value=prior["screening_risks"] or "" if prior else "")
                keywords = st.text_area("ATS keywords: covered / missing / safe to add / do not add", value=prior["ats_keywords"] or "" if prior else "")
                tailoring = st.text_area("Resume changes before applying", value=prior["tailoring_actions"] or "" if prior else "")
                rationale = st.text_area("Decision rationale", value=prior["rationale"] or "" if prior else "")
                save = st.form_submit_button(f"Save {resume['resume_type']} assessment")
                if save:
                    execute("""INSERT INTO assessments(job_id,resume_id,decision,fit_score,strengths,gaps,screening_risks,ats_keywords,tailoring_actions,rationale,assessment_version)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id,resume_id,assessment_version) DO UPDATE SET
                        decision=excluded.decision,fit_score=excluded.fit_score,strengths=excluded.strengths,gaps=excluded.gaps,
                        screening_risks=excluded.screening_risks,ats_keywords=excluded.ats_keywords,
                        tailoring_actions=excluded.tailoring_actions,rationale=excluded.rationale,created_at=CURRENT_TIMESTAMP""",
                        (int(job_id), int(resume.id), decision, int(score) if score else None, strengths, gaps, risks, keywords, tailoring, rationale, "manual-v1"))
                    st.success("Assessment saved.")

elif page == "Applications":
    st.subheader("Application register")
    jobs = query_df("SELECT id,title,company FROM jobs ORDER BY discovered_at DESC")
    resumes = query_df("SELECT id,name FROM resumes WHERE is_active=1 ORDER BY id")
    if jobs.empty:
        st.info("Save a job before recording an application.")
    else:
        with st.form("application_form"):
            job_id = st.selectbox("Job", jobs.id.tolist(), format_func=lambda x: f"#{x} · {jobs.loc[jobs.id==x,'title'].iloc[0]} — {jobs.loc[jobs.id==x,'company'].iloc[0]}")
            resume_opts = [None] + resumes.id.tolist()
            resume_id = st.selectbox("Resume version used", resume_opts, format_func=lambda x: "Not recorded" if x is None else resumes.loc[resumes.id==x,"name"].iloc[0])
            status = st.selectbox("Application status", ["Preparing", "Submitted", "Recruiter response", "Screening", "Interviewing", "On hold", "Rejected", "Withdrawn", "Offer"])
            applied_at = st.date_input("Application date", value=date.today())
            channel = st.selectbox("Application channel", ["LinkedIn", "Naukri", "Indeed", "Company career page", "Referral", "Recruiter", "Email", "Other"])
            expected = st.text_input("Expected compensation")
            followup = st.date_input("Next follow-up date", value=None)
            notes = st.text_area("Notes")
            save = st.form_submit_button("Save application", type="primary")
            if save:
                execute("""INSERT INTO applications(job_id,resume_id,status,applied_at,application_channel,expected_compensation,next_follow_up_at,notes)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (int(job_id), int(resume_id) if resume_id else None, status, applied_at.isoformat(), channel, expected,
                     followup.isoformat() if followup else None, notes))
                execute("UPDATE jobs SET status='Applied', updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(job_id),))
                st.success("Application recorded.")
    st.markdown("### Existing applications")
    df = query_df("""SELECT a.id,j.title,j.company,a.status,a.applied_at,r.name AS resume_used,a.application_channel,a.next_follow_up_at
        FROM applications a JOIN jobs j ON j.id=a.job_id LEFT JOIN resumes r ON r.id=a.resume_id ORDER BY a.applied_at DESC""")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        app_id = st.selectbox("Select application to update", df.id.tolist(), format_func=lambda x: f"#{x} · {df.loc[df.id==x,'title'].iloc[0]} — {df.loc[df.id==x,'company'].iloc[0]}")
        current = query_one("SELECT * FROM applications WHERE id=?", (int(app_id),))
        new_status = st.selectbox("New status", ["Preparing", "Submitted", "Recruiter response", "Screening", "Interviewing", "On hold", "Rejected", "Withdrawn", "Offer"], index=["Preparing", "Submitted", "Recruiter response", "Screening", "Interviewing", "On hold", "Rejected", "Withdrawn", "Offer"].index(current["status"]))
        if st.button("Update application"):
            execute("UPDATE applications SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, int(app_id)))
            st.success("Application updated.")

elif page == "Recruiter Activity":
    st.subheader("Recruiter and hiring-team interactions")
    apps = query_df("SELECT a.id,j.title,j.company FROM applications a JOIN jobs j ON j.id=a.job_id ORDER BY a.applied_at DESC")
    if apps.empty:
        st.info("Record an application first.")
    else:
        with st.form("interaction_form"):
            app_id = st.selectbox("Application", apps.id.tolist(), format_func=lambda x: f"#{x} · {apps.loc[apps.id==x,'title'].iloc[0]} — {apps.loc[apps.id==x,'company'].iloc[0]}")
            kind = st.selectbox("Interaction type", ["Application acknowledgement", "Recruiter response", "Recruiter call", "Interview invitation", "Follow-up sent", "Hiring manager contact", "Rejection", "Other"])
            contact = st.text_input("Contact name")
            role = st.text_input("Contact role")
            channel = st.selectbox("Channel", ["LinkedIn", "Email", "Phone", "WhatsApp", "Platform", "Other"])
            occurred = st.date_input("Date", value=date.today())
            summary = st.text_area("What happened? *")
            response = st.text_area("Response / exact feedback")
            next_action = st.text_input("Next action")
            next_date = st.date_input("Next action date", value=None)
            save = st.form_submit_button("Save interaction")
            if save:
                if not summary.strip():
                    st.error("Add a short interaction summary.")
                else:
                    execute("""INSERT INTO interactions(application_id,interaction_type,contact_name,contact_role,contact_channel,occurred_at,summary,response,next_action,next_action_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (int(app_id),kind,contact,role,channel,occurred.isoformat(),summary,response,next_action,next_date.isoformat() if next_date else None))
                    st.success("Interaction saved.")
    df = query_df("""SELECT i.occurred_at,j.title,j.company,i.interaction_type,i.contact_name,i.summary,i.response,i.next_action,i.next_action_at
        FROM interactions i JOIN applications a ON a.id=i.application_id JOIN jobs j ON j.id=a.job_id ORDER BY i.occurred_at DESC""")
    st.dataframe(df, use_container_width=True, hide_index=True)

elif page == "Interviews & Outcomes":
    st.subheader("Interview rounds")
    apps = query_df("SELECT a.id,j.title,j.company FROM applications a JOIN jobs j ON j.id=a.job_id ORDER BY a.applied_at DESC")
    if apps.empty:
        st.info("Record an application first.")
    else:
        with st.form("interview_form"):
            app_id = st.selectbox("Application", apps.id.tolist(), format_func=lambda x: f"#{x} · {apps.loc[apps.id==x,'title'].iloc[0]} — {apps.loc[apps.id==x,'company'].iloc[0]}", key="interview_app")
            round_name = st.text_input("Round name", placeholder="Recruiter screen / Hiring manager / Technical")
            scheduled = st.text_input("Scheduled date/time (optional)")
            interviewer = st.text_input("Interviewer")
            topics = st.text_area("Topics covered")
            questions = st.text_area("Questions asked")
            feedback = st.text_area("Your feedback / observations")
            result = st.selectbox("Round result", ["Pending", "Passed", "Rejected", "Rescheduled", "No-show"])
            save = st.form_submit_button("Save interview round")
            if save:
                if round_name.strip():
                    execute("""INSERT INTO interviews(application_id,round_name,scheduled_at,interviewer,topics,questions,feedback,result)
                        VALUES(?,?,?,?,?,?,?,?)""", (int(app_id),round_name,scheduled,interviewer,topics,questions,feedback,result))
                    st.success("Interview round saved.")
                else:
                    st.error("Round name is required.")
    st.markdown("### Record final outcome")
    if not apps.empty:
        with st.form("outcome_form"):
            outcome_app = st.selectbox("Application", apps.id.tolist(), format_func=lambda x: f"#{x} · {apps.loc[apps.id==x,'title'].iloc[0]} — {apps.loc[apps.id==x,'company'].iloc[0]}", key="outcome_app")
            outcome = st.selectbox("Outcome", ["Pending", "Rejected", "Offer", "Withdrawn", "Position closed", "No response"])
            reason = st.text_input("Reason (if known)")
            feedback = st.text_area("Employer feedback / evidence")
            save_outcome = st.form_submit_button("Save outcome")
            if save_outcome:
                execute("""INSERT INTO outcomes(application_id,outcome,reason,feedback) VALUES(?,?,?,?)
                    ON CONFLICT(application_id) DO UPDATE SET outcome=excluded.outcome,reason=excluded.reason,feedback=excluded.feedback,recorded_at=CURRENT_TIMESTAMP""",
                    (int(outcome_app),outcome,reason,feedback))
                st.success("Outcome saved.")
    st.markdown("### Interview history")
    hist = query_df("""SELECT i.id,j.title,j.company,i.round_name,i.scheduled_at,i.interviewer,i.result
        FROM interviews i JOIN applications a ON a.id=i.application_id JOIN jobs j ON j.id=a.job_id ORDER BY i.created_at DESC""")
    st.dataframe(hist, use_container_width=True, hide_index=True)

elif page == "Learning Log":
    st.subheader("Improvement experiments")
    st.caption("Use this to test one change at a time and compare outcomes. Small samples are directional, not proof.")
    with st.form("experiment_form"):
        hypothesis = st.text_area("Hypothesis *", placeholder="Example: A clearer technical delivery headline may improve recruiter response for Technical PM roles.")
        change = st.text_area("Change being tested *")
        start = st.date_input("Cohort start", value=date.today())
        end = st.date_input("Cohort end", value=None)
        status = st.selectbox("Status", ["Planned", "Running", "Completed", "Abandoned"])
        result = st.text_area("Observed result")
        save = st.form_submit_button("Save experiment")
        if save:
            if hypothesis.strip() and change.strip():
                execute("INSERT INTO improvement_experiments(hypothesis,change_made,cohort_start,cohort_end,status,result) VALUES(?,?,?,?,?,?)",
                    (hypothesis,change,start.isoformat(),end.isoformat() if end else None,status,result))
                st.success("Experiment saved.")
            else:
                st.error("Hypothesis and change are required.")
    experiments = query_df("SELECT id,hypothesis,change_made,cohort_start,cohort_end,status,result FROM improvement_experiments ORDER BY created_at DESC")
    st.dataframe(experiments, use_container_width=True, hide_index=True)

st.divider()
st.caption("Job Radar records evidence; it does not automatically infer fit, posting freshness, or hiring outcomes. Keep source facts and your interpretation separate.")
