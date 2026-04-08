import re
from urllib.parse import urljoin

import scrapy


class HuurwoningenSpider(scrapy.Spider):
    name = "huurwoningen"
    allowed_domains = ["huurwoningen.nl"]
    start_urls = [
        "https://www.huurwoningen.nl/en/appartement/huren/enschede/",
        "https://www.huurwoningen.nl/en/studio/huren/enschede/",
    ]

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
        },
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1,
    }

    seen_ids = set()

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        # даём странице дорисоваться
                        scrapy.http.request.NO_CALLBACK,  # harmless placeholder if env ignores
                    ],
                },
                errback=self.errback_close_page,
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]

        try:
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass

        try:
            await page.wait_for_selector("section.listing-search-item--for-rent", timeout=15000)
        except Exception:
            self.logger.warning("No listing cards found on %s", response.url)

        html = await page.content()
        await page.close()

        response = response.replace(body=html)

        cards = response.css("section.listing-search-item--for-rent")

        for card in cards:
            listing_id = card.attrib.get("data-listing-search-item-id")
            if listing_id and listing_id in self.seen_ids:
                continue
            if listing_id:
                self.seen_ids.add(listing_id)

            rel_url = card.css("a.listing-search-item__link--title::attr(href)").get()
            url = urljoin(response.url, rel_url) if rel_url else None

            title = self.clean(
                card.css("a.listing-search-item__link--title::text").get()
            )

            subtitle = self.clean(
                card.css(".listing-search-item__sub-title::text").get()
            )

            price_text = self.clean(
                card.css(".listing-search-item__price-main::text").get()
            )
            price = self.parse_price(price_text)

            feature_texts = [
                self.clean(x)
                for x in card.css(".illustrated-features__item::text").getall()
            ]
            feature_texts = [x for x in feature_texts if x]

            size = self.parse_size(feature_texts)
            rooms = self.parse_rooms(feature_texts)
            interior = self.parse_interior(feature_texts)

            image = card.css(".picture__image::attr(src)").get()
            landlord = None

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
                "source": "huurwoningen",
            }

        next_page = self.get_next_page(response)
        if next_page:
            yield scrapy.Request(
                url=urljoin(response.url, next_page),
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                },
                errback=self.errback_close_page,
            )

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()

    def get_next_page(self, response):
        selectors = [
            'a[rel="next"]::attr(href)',
            'a.pagination__link--next::attr(href)',
            'a[aria-label*="Next"]::attr(href)',
            'a[aria-label*="next"]::attr(href)',
        ]
        for selector in selectors:
            href = response.css(selector).get()
            if href:
                return href
        return None

    def clean(self, value):
        if not value:
            return None
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    def parse_price(self, text):
        if not text:
            return None

        m = re.search(r"€\s*([\d.,]+)", text)
        if not m:
            return None

        raw = m.group(1)

        # 500 -> 500
        # 1.090 -> 1090
        # 1.450 -> 1450
        if "." in raw and "," not in raw:
            parts = raw.split(".")
            if len(parts[-1]) == 3:
                raw = "".join(parts)
            else:
                raw = raw.replace(".", "")
        else:
            raw = raw.replace(".", "").replace(",", ".")

        try:
            value = float(raw)
            return int(value) if value.is_integer() else value
        except ValueError:
            return None

    def parse_size(self, features):
        for f in features:
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", f, re.I)
            if m:
                value = float(m.group(1).replace(",", "."))
                return int(value) if value.is_integer() else value
        return None

    def parse_rooms(self, features):
        for f in features:
            m = re.search(r"(\d+)\s*room", f, re.I)
            if m:
                return int(m.group(1))
        return None

    def parse_interior(self, features):
        known = {"Furnished", "Upholstered", "Shell", "Unfurnished"}
        for f in features:
            if f in known:
                return f
        return None