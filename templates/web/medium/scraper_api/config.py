# Template source: scrapy + fastapi pattern | Difficulty: medium | Niche: web
HOST = "0.0.0.0"
PORT = {{PORT}}  # e.g. 8000
PLAYWRIGHT_HEADLESS = True
DB_PATH = "jobs.db"
MAX_CONCURRENT_JOBS = {{MAX_CONCURRENT_JOBS}}  # e.g. 5
RATE_LIMIT = "{{RATE_LIMIT}}"  # e.g. 10/minute
