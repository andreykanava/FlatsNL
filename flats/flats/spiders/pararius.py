import re
import scrapy


class ParariusSpider(scrapy.Spider):
    name = "pararius"
    allowed_domains = ["pararius.com"]
    start_urls = ["https://www.pararius.com/apartments/enschede/studio"]
    handle_httpstatus_list = [403, 429]

    custom_settings = {
        "LOG_LEVEL": "INFO",
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    def parse(self, response):
        if response.status == 403:
            self.logger.warning("Access denied by Pararius: HTTP 403 for %s", response.url)
            self.logger.warning("Response preview:\n%s", response.text[:1000])
            return

        if response.status == 429:
            self.logger.warning("Rate limited by Pararius: HTTP 429 for %s", response.url)
            return

        cards = response.css("li.search-list__item--listing section.listing-search-item")
        self.logger.info("Found %d cards", len(cards))

        if not cards:
            self.logger.warning("No listing cards found on %s", response.url)
            self.logger.warning("Response preview:\n%s", response.text[:2000])
            return

        for card in cards:
            title = self.clean(card.css("h3.listing-search-item__title a::text").get())
            href = card.css("h3.listing-search-item__title a::attr(href)").get()
            url = response.urljoin(href) if href else None

            subtitle = self.clean(card.css("div.listing-search-item__sub-title::text").get())

            price_raw = self.clean(card.css("span.listing-search-item__price-main::text").get())
            price = self.parse_price(price_raw)

            features = [self.clean(x) for x in card.css("ul.illustrated-features li::text").getall()]
            features = [x for x in features if x]

            size = features[0] if len(features) > 0 else None
            rooms = features[1] if len(features) > 1 else None
            interior = features[2] if len(features) > 2 else None

            landlord = self.clean(card.css("div.listing-search-item__info a::text").get())
            image = card.css("a.listing-search-item__link--depiction img::attr(src)").get()
            image = response.urljoin(image) if image else None

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

    @staticmethod
    def clean(value):
        if value is None:
            return None
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    @staticmethod
    def parse_price(value):
        if not value:
            return None
        digits = re.sub(r"[^\d]", "", value)
        return int(digits) if digits else None