# Template source: scrapy + fastapi pattern | Difficulty: medium | Niche: web
import uvicorn
from api import app
from config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, reload=False)
