# Template source: scrapy + fastapi pattern | Difficulty: medium | Niche: web
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import uuid, sqlite3
from scraper import scrape_url
from config import DB_PATH

app = FastAPI(title="{{API_TITLE}}")

class ScrapeRequest(BaseModel):
    url: str
    selectors: dict  # {"field": "css_selector"}
    # {{ADD_MORE_OPTIONS}}

class JobStatus(BaseModel):
    job_id: str
    status: str
    result: dict | None = None

def get_db():
    return sqlite3.connect(DB_PATH)

@app.post("/scrape", response_model=JobStatus)
async def create_job(req: ScrapeRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    # {{STORE_JOB_IN_DB}}
    bg.add_task(run_scrape, job_id, req)
    return JobStatus(job_id=job_id, status="queued")

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    # {{FETCH_JOB_FROM_DB}}
    return JobStatus(job_id=job_id, status="{{STATUS}}")

async def run_scrape(job_id: str, req: ScrapeRequest):
    result = await scrape_url(req.url, req.selectors)
    # {{UPDATE_JOB_STATUS_IN_DB}}
