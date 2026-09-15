from dataclasses import dataclass
from datetime import datetime


@dataclass
class Job:
    source: str
    source_job_id: str
    company: str
    title: str
    location: str
    workplace_type: str
    first_published: datetime | None
    updated_at: datetime | None
    application_url: str
    description: str
