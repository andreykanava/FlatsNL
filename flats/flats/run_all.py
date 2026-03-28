import time
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from spiders.kamernet import KamernetSpider
from spiders.pararius import ParariusSpider
from spiders.roomspot import RoomspotSpider


INTERVAL_SECONDS = 300  # 5 минут


def run_once():
    process = CrawlerProcess(get_project_settings())

    process.crawl(KamernetSpider)
    process.crawl(ParariusSpider)
    process.crawl(RoomspotSpider)

    process.start()


if __name__ == "__main__":
    while True:
        print("=== Starting scrape cycle ===")
        try:
            run_once()
        except Exception as e:
            print(f"Cycle failed: {e}")
        print(f"=== Sleeping {INTERVAL_SECONDS} seconds ===")
        time.sleep(INTERVAL_SECONDS)