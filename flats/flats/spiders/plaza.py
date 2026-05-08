import re
import scrapy
from scrapy_playwright.page import PageMethod


class PlazaSpider(scrapy.Spider):
    name = "plaza"
    allowed_domains = ["plaza.newnewnew.space"]
    start_urls = [
        "https://plaza.newnewnew.space/en/availables-places/living-place"
        "#?gesorteerd-op=zoekprofiel&locatie=Enschede-Nederland%2B-%2BOverijssel"
    ]

    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "LOG_LEVEL": "INFO",
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                        PageMethod("wait_for_selector", "section.list-item", timeout=20000),
                    ],
                },
            )

    def parse(self, response):
        self.logger.info("Parse started: %s", response.url)

        cards = response.css("section.list-item")
        self.logger.info("Found %d Plaza cards", len(cards))

        if not cards:
            self.logger.warning("No Plaza cards found")
            self.logger.warning("Response preview:\n%s", response.text[:2000])
            return

        for idx, card in enumerate(cards, start=1):
            tile_id = card.css("div[id^='object-tile-']::attr(id)").get()
            listing_id = self.extract_listing_id(tile_id)

            href = card.css('a[href*="/availables-places/living-place/details/"]::attr(href)').get()
            if not href:
                href = card.css("div[id^='object-tile-'] > a::attr(href)").get()
            url = response.urljoin(href) if href else None

            image = card.css("span.object-afbeelding img::attr(src)").get()
            if image:
                image = response.urljoin(image)

            street = self.clean(" ".join(card.css(".object-address .address-part:first-child *::text").getall()))
            if not street:
                street = self.clean(" ".join(card.css(".object-address .address-part:first-child::text").getall()))

            city_text = self.clean(" ".join(card.css(".object-address .address-part:nth-child(2) *::text").getall()))
            if not city_text:
                city_text = self.clean(" ".join(card.css(".object-address .address-part:nth-child(2)::text").getall()))

            city, district = self.parse_city_and_district(city_text)

            price_raw = self.clean(" ".join(card.css(".properties .prijs::text").getall()))
            price_total = self.parse_money(price_raw)

            total_rent_raw = self.clean(" ".join(card.css(".kosten-regel2::text").getall()))
            total_rent = self.parse_money(total_rent_raw)

            dwelling_type = self.clean(card.css(".woningtype::text").get())

            floor_text = self.clean(" ".join(card.css(".verdieping ::text").getall()))
            floor = self.extract_floor(floor_text)

            available_from = self.clean(" ".join(card.css(".beschikbaarPer ::text").getall()))

            area_text = self.extract_area_text(card)
            area_m2 = self.parse_area(area_text)

            labels = [self.clean(x) for x in card.css(".object-label-value::text").getall()]
            labels = [x for x in labels if x]

            deadline = self.clean(" ".join(card.css(".reageren-binnen::text").getall()))
            reactions_text = self.clean(card.css(".aantal-reacties .amount::text").get())
            reactions = int(reactions_text) if reactions_text and reactions_text.isdigit() else None

            yield {
                "listing_id": listing_id,
                "url": url,
                "image": image,
                "street": street,
                "city": city,
                "district": district,
                "price_total": price_total,
                "price_total_raw": price_raw,
                "total_rent": total_rent,
                "total_rent_raw": total_rent_raw,
                "dwelling_type": dwelling_type,
                "floor": floor,
                "floor_raw": floor_text,
                "available_from": available_from,
                "area_m2": area_m2,
                "area_raw": area_text,
                "labels": labels,
                "deadline": deadline,
                "reactions": reactions,
                "source": "plaza",
            }

            self.logger.info(
                "[%d/%d] %s | %s | %s",
                idx,
                len(cards),
                street,
                price_total or total_rent,
                url,
            )

    def extract_listing_id(self, value):
        if not value:
            return None

        match = re.search(r"object-tile-(\d+)", value)
        return match.group(1) if match else None

    def parse_city_and_district(self, value):
        if not value:
            return None, None

        parts = [self.clean(x) for x in value.split("|")]
        parts = [x for x in parts if x]

        city = parts[0] if len(parts) >= 1 else None
        district = parts[1] if len(parts) >= 2 else None
        return city, district

    def extract_area_text(self, card):
        for text in card.css(".object-label-value::text").getall():
            text = self.clean(text)
            if text and "m²" in text:
                return text
        return None

    def clean(self, value):
        if value is None:
            return None

        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    def parse_money(self, value):
        if not value:
            return None

        value = value.replace("€", "").replace(",", "").strip()

        match = re.search(r"(\d+(?:\.\d+)?)", value)
        return float(match.group(1)) if match else None

    def parse_area(self, value):
        if not value:
            return None

        match = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", value)
        if not match:
            return None

        return float(match.group(1).replace(",", "."))

    def extract_floor(self, value):
        if not value:
            return None

        value = self.clean(value.replace("•", ""))
        return value or None
