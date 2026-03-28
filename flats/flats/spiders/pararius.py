import scrapy
import re

class ParariusSpider(scrapy.Spider):
    name = "pararius"
    allowed_domains = ["pararius.com"]
    start_urls = ["https://www.pararius.com/apartments/enschede/studio"]

    def parse(self, response):
        cards = response.css("li.search-list__item--listing section.listing-search-item")

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

            features = card.css("ul.illustrated-features li::text").getall()
            features = [x.strip() for x in features if x.strip()]

            size = features[0] if len(features) > 0 else None
            rooms = features[1] if len(features) > 1 else None
            interior = features[2] if len(features) > 2 else None

            landlord = card.css("div.listing-search-item__info a::text").get()
            landlord = landlord.strip() if landlord else None

            image = card.css("a.listing-search-item__link--depiction img::attr(src)").get()

            is_new = bool(card.css("span.listing-label--new"))

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
