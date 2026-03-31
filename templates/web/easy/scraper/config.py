# Template source: scrapy/scrapy | Difficulty: easy | Niche: web
START_URLS = ["{{TARGET_URL}}"]
ALLOWED_DOMAINS = ["{{DOMAIN}}"]
OUTPUT_FORMAT = "{{OUTPUT_FORMAT}}"  # json, csv, sqlite
OUTPUT_PATH = "output/results.{{OUTPUT_FORMAT}}"
DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS = 4
