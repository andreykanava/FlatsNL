import re
import scrapy
from scrapy_playwright.page import PageMethod


class RoomspotSpider(scrapy.Spider):
    name = "roomspot"
    allowed_domains = ["roomspot.nl"]

    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "LOG_LEVEL": "INFO",
        # чтобы видеть yield items
        "FEEDS": {
            "roomspot.json": {
                "format": "json",
                "overwrite": True,
                "encoding": "utf-8",
                "indent": 2,
            }
        },
    }

    def start_requests(self):
        url = "https://www.roomspot.nl/en/housing-offer/to-rent#?gesorteerd-op=prijs%2B&woningtype=2"

        yield scrapy.Request(
            url=url,
            meta={
                "playwright": True,
                "playwright_include_page": False,
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "networkidle"),
                    PageMethod("wait_for_selector", "section.list-item", timeout=20000),
                ],
            },
            callback=self.parse,
        )

    def parse(self, response):
        self.logger.info("Parse started: %s", response.url)

        cards = response.css("section.list-item")
        self.logger.info("Found %d cards", len(cards))

        if not cards:
            self.logger.warning("No cards found")
            self.logger.warning("Response preview:\n%s", response.text[:2000])
            return

        for idx, card in enumerate(cards, start=1):
            item = {}

            tile_id = card.css("div[id^='object-tile-']::attr(id)").get()
            listing_id = None
            if tile_id:
                m = re.search(r"object-tile-(\d+)", tile_id)
                if m:
                    listing_id = m.group(1)

            href = card.css('a[href*="/housing-offer/"]::attr(href)').get()
            url = response.urljoin(href) if href else None

            image = card.css("span.object-afbeelding img::attr(src)").get()
            if image:
                image = response.urljoin(image)

            street = self.clean(" ".join(card.css(".object-address .address-part:first-child *::text").getall()))
            if not street:
                street = self.clean(card.css(".object-address .address-part:first-child::text").get())

            city_text = self.clean(" ".join(card.css(".object-address .address-part:nth-child(2) *::text").getall()))
            if not city_text:
                city_text = self.clean(" ".join(card.css(".object-address .address-part:nth-child(2)::text").getall()))

            city = None
            district = None
            if city_text:
                parts = [self.clean(x) for x in city_text.split("|")]
                parts = [x for x in parts if x]
                if len(parts) >= 1:
                    city = parts[0]
                if len(parts) >= 2:
                    district = parts[1]

            price_raw = self.clean(" ".join(card.css(".properties .prijs::text").getall()))
            price = self.parse_money(price_raw)

            basic_rent_raw = self.clean(" ".join(card.css(".kosten-regel2::text").getall()))
            basic_rent = self.parse_money(basic_rent_raw)

            dwelling_type = self.clean(card.css(".woningtype::text").get())

            floor_text = self.clean(" ".join(card.css(".verdieping ::text").getall()))
            floor = self.extract_floor(floor_text)

            available_from = self.clean(" ".join(card.css(".beschikbaarPer ::text").getall()))

            area_text = None
            for txt in card.css(".object-label-value::text").getall():
                txt = self.clean(txt)
                if txt and "m²" in txt:
                    area_text = txt
                    break
            area_m2 = self.parse_area(area_text)

            rent_benefit = False
            housemates = None
            selection_model = None

            for txt in card.css(".object-label-value::text").getall():
                txt = self.clean(txt)
                if not txt:
                    continue

                if "Rent benefit" in txt:
                    rent_benefit = True

                if "housemate" in txt.lower():
                    housemates = txt

                if "Random selection" in txt:
                    selection_model = txt

            reactions_text = self.clean(card.css(".aantal-reacties .amount::text").get())
            reactions = int(reactions_text) if reactions_text and reactions_text.isdigit() else None

            deadline = self.clean(" ".join(card.css(".reageren-binnen::text").getall()))

            item["listing_id"] = listing_id
            item["url"] = url
            item["image"] = image
            item["street"] = street
            item["city"] = city
            item["district"] = district
            item["price_total"] = price
            item["price_total_raw"] = price_raw
            item["basic_rent"] = basic_rent
            item["basic_rent_raw"] = basic_rent_raw
            item["dwelling_type"] = dwelling_type
            item["floor"] = floor
            item["floor_raw"] = floor_text
            item["available_from"] = available_from
            item["area_m2"] = area_m2
            item["area_raw"] = area_text
            item["rent_benefit"] = rent_benefit
            item["housemates"] = housemates
            item["selection_model"] = selection_model
            item["deadline"] = deadline
            item["source"] = "roomspot"

            self.logger.info(
                "[%d/%d] %s | %s | %s | reactions=%s",
                idx,
                len(cards),
                street,
                price,
                url,
                reactions,
            )

            yield item

    def clean(self, value):
        if value is None:
            return None
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    def parse_money(self, value):
        if not value:
            return None

        value = value.replace("€", "").replace("Basic rent:", "").strip()
        value = value.replace(",", "")

        m = re.search(r"(\d+(?:\.\d+)?)", value)
        return float(m.group(1)) if m else None

    def parse_area(self, value):
        if not value:
            return None

        m = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", value)
        if not m:
            return None

        return float(m.group(1).replace(",", "."))

    def extract_floor(self, value):
        if not value:
            return None

        value = self.clean(value)
        if not value:
            return None

        value = value.replace("•", "").strip()
        return value or None