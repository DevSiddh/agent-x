# Template source: scrapy/scrapy | Difficulty: easy | Niche: web
import csv, json, sqlite3
from config import OUTPUT_FORMAT, OUTPUT_PATH

class StoragePipeline:
    def open_spider(self, spider):
        self.items = []

    def process_item(self, item, spider):
        self.items.append(dict(item))
        return item

    def close_spider(self, spider):
        if OUTPUT_FORMAT == "csv":
            with open(OUTPUT_PATH, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.items[0].keys())
                writer.writeheader()
                writer.writerows(self.items)
        elif OUTPUT_FORMAT == "json":
            with open(OUTPUT_PATH, "w") as f:
                json.dump(self.items, f, indent=2)
