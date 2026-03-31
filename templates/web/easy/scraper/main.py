# Template source: scrapy/scrapy | Difficulty: easy | Niche: web
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from spider import {{SPIDER_NAME}}Spider

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())
    process.crawl({{SPIDER_NAME}}Spider)
    process.start()
