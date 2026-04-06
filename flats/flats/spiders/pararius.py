import re
import scrapy

class ParariusSpider(scrapy.Spider):
    name = "pararius"
    allowed_domains = ["pararius.com"]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "HTTPERROR_ALLOWED_CODES": [403],
        # avoid br until brotli is installed
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Upgrade-Insecure-Requests": "1",
        },
        # let Playwright provide a browser UA more naturally
        "USER_AGENT": None,
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
        },
    }

    async def start(self):
        yield scrapy.Request(
            url="https://www.pararius.com/apartments/enschede/studio",
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_include_page": True,
            },
            headers={
                "Referer": "https://www.pararius.com/",
            },
        )

    # optional backward compatibility for older Scrapy
    def start_requests(self):
        yield scrapy.Request(
            url="https://www.pararius.com/apartments/enschede/studio",
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_include_page": True,
            },
            headers={
                "Referer": "https://www.pararius.com/",
            },
        )

    async def parse(self, response):
        self.logger.info("STATUS = %s", response.status)

        if response.status == 403:
            self.logger.info("403 BODY PREVIEW:\n%s", response.text[:2000])
            return

        page = response.meta["playwright_page"]

        # give JS / anti-bot challenge time
        await page.wait_for_timeout(5000)

        html = await page.content()
        await page.close()

        response = response.replace(body=html)

        cards = response.css("li.search-list__item--listing section.listing-search-item")

        self.logger.info("Found %d cards", len(cards))

        for card in cards:
            title = card.css("h3.listing-search-item__title a::text").get()
            title = title.strip() if title else None

            href = card.css("h3.listing-search-item__title a::attr(href)").get()
            url = response.urljoin(href) if href else None

            subtitle = card.css("div.listing-search-item__sub-title::text").get()
            subtitle = subtitle.strip() if subtitle else None

            price_raw = card.css("span.listing-search-item__price-main::text").get()
            price_raw = price_raw.strip() if price_raw else None
            price = int(re.sub(r"[^\d]", "", price_raw)) if price_raw else None

            features = [x.strip() for x in card.css("ul.illustrated-features li::text").getall() if x.strip()]
            size = features[0] if len(features) > 0 else None
            rooms = features[1] if len(features) > 1 else None
            interior = features[2] if len(features) > 2 else None

            landlord = card.css("div.listing-search-item__info a::text").get()
            landlord = landlord.strip() if landlord else None

            image = card.css("a.listing-search-item__link--depiction img::attr(src)").get()

            yield {
                "url": url,
                "title": title,
                "address": subtitle,
                "price": price,
                "size": size,
                "rooms": rooms,
                "interior": interior,
                "landlord": landlord,
                "image": image,
                "source": "pararius",
            }