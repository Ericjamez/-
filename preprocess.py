# ==========================================================
# Scrapy 新闻爬虫实验手册 —— Jupyter 单文件完整版
# 严格对应实验手册内容 | 直接运行 | 自动保存 JSON
# ==========================================================

# 1. 自动安装依赖
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "scrapy", "pandas"])

# 2. 导入库
import os
import json
import scrapy
import pandas as pd
from datetime import datetime
from scrapy.crawler import CrawlerProcess
from scrapy.exceptions import DropItem

# ==========================================
# 对应实验手册：Item 定义 (items.py)
# ==========================================
class NewsItem(scrapy.Item):
    title = scrapy.Field()
    publish_time = scrapy.Field()
    content = scrapy.Field()
    url = scrapy.Field()
    source = scrapy.Field()

# ==========================================
# 对应实验手册：Pipeline (pipelines.py)
# ==========================================
class NewsCrawlerPipeline:
    def __init__(self):
        self.items = []

    def open_spider(self, spider):
        if not os.path.exists("output"):
            os.makedirs("output")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = f"output/news_{ts}.json"

    def process_item(self, item, spider):
        if not item.get("title"):
            raise DropItem("空标题，已跳过")
        item["content"] = " ".join(item["content"].split())
        self.items.append(dict(item))
        return item

    def close_spider(self, spider):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 数据已保存到：{self.filename}")
        print(f"📊 共保存 {len(self.items)} 条数据")

# ==========================================
# 对应实验手册：Spider 爬虫 (news_spider.py)
# ==========================================
class NewsSpider(scrapy.Spider):
    name = "news"
    allowed_domains = ["quotes.toscrape.com"]
    start_urls = ["http://quotes.toscrape.com/"]
    max_pages = 5
    current_page = 0

    def parse(self, response):
        self.current_page += 1
        quotes = response.css("div.quote")

        for quote in quotes:
            item = NewsItem()
            item["title"] = self.extract_title(quote)
            item["publish_time"] = self.extract_author(quote)
            item["content"] = self.extract_content(quote)
            item["url"] = response.url
            item["source"] = "quotes.toscrape.com"
            yield item

        if self.current_page < self.max_pages:
            next_page = response.css("li.next a::attr(href)").get()
            if next_page:
                yield response.follow(next_page, callback=self.parse)

    def extract_title(self, quote):
        title = quote.css("span.text::text").get("")
        return title.strip('""').strip()

    def extract_author(self, quote):
        return quote.css("small.author::text").get("未知作者")

    def extract_content(self, quote):
        tags = quote.css("div.tags a.tag::text").getall()
        return f"标签: {', '.join(tags)}"

# ==========================================
# 对应实验手册：Settings (settings.py)
# ==========================================
settings = {
    "BOT_NAME": "news_crawler",
    "ROBOTSTXT_OBEY": True,
    "DOWNLOAD_DELAY": 1,
    "LOG_LEVEL": "INFO",
    "FEED_EXPORT_ENCODING": "utf-8",
    "DEFAULT_REQUEST_HEADERS": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "ITEM_PIPELINES": {
        NewsCrawlerPipeline: 300
    },
    "AUTOTHROTTLE_ENABLED": True
}

# ==========================================
# 启动爬虫
# ==========================================
print("🚀 启动 Scrapy 新闻爬虫（对应实验手册）...")
process = CrawlerProcess(settings=settings)
process.crawl(NewsSpider)
process.start()

# ==========================================
# 自动展示结果
# ==========================================
files = sorted(os.listdir("output"))
latest_file = f"output/{files[-1]}"

with open(latest_file, encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)
print("\n✅ 爬取完成，前 5 条数据预览：")
display(df.head())