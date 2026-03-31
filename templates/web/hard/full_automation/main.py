# Template source: seleniumbase/seleniumbase | Difficulty: hard | Niche: web
import asyncio
from scheduler import start as start_scheduler

if __name__ == "__main__":
    start_scheduler()
    asyncio.get_event_loop().run_forever()
