from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from spiders.kamernet import KamernetSpider
from spiders.pararius import ParariusSpider
from spiders.roomspot import RoomspotSpider

process = CrawlerProcess(get_project_settings())

process.crawl(KamernetSpider)
process.crawl(ParariusSpider)
process.crawl(RoomspotSpider)

process.start()