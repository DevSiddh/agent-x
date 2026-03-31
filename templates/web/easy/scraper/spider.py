# Template source: scrapy/scrapy | Difficulty: easy | Niche: web
import scrapy
from config import START_URLS, ALLOWED_DOMAINS

class {{SPIDER_NAME}}Spider(scrapy.Spider):
    name = "{{SPIDER_NAME}}"
    allowed_domains = ALLOWED_DOMAINS
    start_urls = START_URLS

    def parse(self, response):
        # Core engine: extract items using CSS/XPath selectors
        for item in response.css("{{ITEM_SELECTOR}}"):
            yield {
                "title": item.css("{{TITLE_SELECTOR}}::text").get(),
                "url": item.css("{{URL_SELECTOR}}::attr(href)").get(),
                "price": item.css("{{PRICE_SELECTOR}}::text").get(),
                # {{ADD_MORE_FIELDS}}
            }
        # Follow pagination
        next_page = response.css("{{NEXT_PAGE_SELECTOR}}::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)
