import scrapy
import re


class KamernetSpider(scrapy.Spider):
    name = "kamernet"
    allowed_domains = ["kamernet.nl"]
    start_urls = [
        "https://kamernet.nl/huren/studio-enschede?radius=5&minSize=0&maxRent=0",

    ]

    def parse(self, response):
        cards = response.css("a.SearchResultCard_root__hSxn3")

        for card in cards:
            url = response.urljoin(card.attrib["href"])

            rows = card.css("div.SearchResultCard_contentRow__VZIJY")

            # 1-я строка: улица + город
            address_parts = rows[0].css("span::text").getall() if len(rows) > 0 else []
            address_parts = [x.strip() for x in address_parts if x.strip() and x.strip() != ","]

            street = address_parts[0].replace(",", "").strip() if len(address_parts) > 0 else None
            city = address_parts[1].replace(",", "").strip() if len(address_parts) > 1 else None

            # 2-я строка: размер / furnishing / type
            detail_parts = rows[1].css("p::text").getall() if len(rows) > 1 else []
            detail_parts = [x.strip() for x in detail_parts if x.strip()]

            size = detail_parts[0] if len(detail_parts) > 0 else None
            furnishing = detail_parts[1] if len(detail_parts) > 1 else None
            type_ = detail_parts[2] if len(detail_parts) > 2 else None

            # 3-я строка: availability
            availability = rows[2].css("p::text").get(default="").strip() if len(rows) > 2 else None

            # 4-я строка: price
            price_raw = rows[3].css("span::text").get() if len(rows) > 3 else None
            price = int(re.sub(r"\D", "", price_raw)) if price_raw else None

            yield {
                "url": url,
                "street": street,
                "city": city,
                "size": size,
                "furnishing": furnishing,
                "type": type_,
                "availability": availability,
                "price": price,
                "source": "kamernet",
            }