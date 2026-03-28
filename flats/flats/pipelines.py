import hashlib
from datetime import datetime, timezone

import requests
from pymongo import MongoClient



class FlatsPipeline:
    def __init__(self, mongo_uri, mongo_db, telegram_token, telegram_chat_id):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.client = None
        self.db = None
        self.col = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DATABASE", "housing"),
            telegram_token=crawler.settings.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=crawler.settings.get("TELEGRAM_CHAT_ID"),
        )

    def open_spider(self, spider):
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.col = self.db["listings"]

        self.col.create_index("uid", unique=True)
        self.col.create_index([("source", 1), ("created_at", -1)])
        self.col.create_index([("city", 1), ("price", 1)])

        spider.logger.info("Mongo pipeline started")

    def close_spider(self, spider):
        if self.client:
            self.client.close()
        spider.logger.info("Mongo pipeline closed")

    def process_item(self, item, spider):
        item = dict(item)
        normalized = self.normalize_item(item)

        now = datetime.now(timezone.utc)

        filter_doc = {"uid": normalized["uid"]}
        update_doc = {
            "$set": {
                "source": normalized.get("source"),
                "source_id": normalized.get("source_id"),
                "url": normalized.get("url"),
                "title": normalized.get("title"),
                "street": normalized.get("street"),
                "city": normalized.get("city"),
                "district": normalized.get("district"),
                "address": normalized.get("address"),
                "price": normalized.get("price"),
                "size": normalized.get("size"),
                "rooms": normalized.get("rooms"),
                "image": normalized.get("image"),
                "availability": normalized.get("availability"),
                "raw": normalized.get("raw"),
                "updated_at": now,
            },
            "$setOnInsert": {
                "uid": normalized["uid"],
                "created_at": now,
            },
        }

        result = self.col.update_one(filter_doc, update_doc, upsert=True)

        is_new = result.upserted_id is not None

        self.pretty_print_listing(normalized, is_new)

        if is_new:
            spider.logger.info("NEW listing saved: %s", normalized["uid"])

            telegram_doc = {
                **normalized,
                "created_at": now,
                "updated_at": now,
            }
            self.send_telegram_message(telegram_doc)
        else:
            spider.logger.info("Existing listing updated: %s", normalized["uid"])

        return item

    def normalize_item(self, item):
        source = item.get("source")
        listing_id = item.get("listing_id")
        url = item.get("url")

        uid = self.build_uid(source, listing_id, url)

        normalized = {
            "uid": uid,
            "source": source,
            "source_id": listing_id,
            "url": url,
            "title": self.pick_title(item),
            "street": item.get("street"),
            "city": item.get("city"),
            "district": item.get("district"),
            "address": item.get("address"),
            "price": self.pick_price(item),
            "size": self.pick_size(item),
            "rooms": self.to_int(item.get("rooms")),
            "image": item.get("image"),
            "availability": item.get("availability") or item.get("available_from"),
            "raw": item,
        }

        return normalized

    def build_uid(self, source, listing_id, url):
        if listing_id:
            base = f"{source}:{listing_id}"
        else:
            base = f"{source}:{url}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def pick_title(self, item):
        return (
            item.get("title")
            or item.get("street")
            or item.get("address")
            or "No title"
        )

    def pick_price(self, item):
        return (
            self.to_float(item.get("price"))
            or self.to_float(item.get("price_total"))
            or self.to_float(item.get("basic_rent"))
        )

    def pick_size(self, item):
        return (
            self.to_float(item.get("size"))
            or self.to_float(item.get("area_m2"))
        )

    def to_float(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        s = str(value).strip()
        s = s.replace("€", "").replace("m²", "").replace(",", ".")
        import re
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        return float(m.group(1)) if m else None

    def to_int(self, value):
        if value is None:
            return None
        if isinstance(value, int):
            return value

        import re
        m = re.search(r"(\d+)", str(value))
        return int(m.group(1)) if m else None

    def send_telegram_message(self, doc):
        if not self.telegram_token or not self.telegram_chat_id:
            return

        text = self.format_message(doc)

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
        except Exception:
            pass

    def format_message(self, doc):
        raw = doc.get("raw", {})
        source = doc.get("source", "-")
        title = self.escape(doc.get("title"))
        price = doc.get("price")
        size = doc.get("size")
        city = self.escape(doc.get("city"))
        street = self.escape(doc.get("street"))
        district = self.escape(doc.get("district"))
        address = self.escape(doc.get("address"))
        availability = self.escape(doc.get("availability"))
        url = doc.get("url")

        lines = [
            "🏠 <b>New listing</b>",
            f"<b>Source:</b> {self.escape(source)}",
            f"<b>Title:</b> {title}",
        ]

        if street:
            lines.append(f"<b>Street:</b> {street}")
        if city:
            lines.append(f"<b>City:</b> {city}")
        if district:
            lines.append(f"<b>District:</b> {district}")
        if address:
            lines.append(f"<b>Address:</b> {address}")
        if price is not None:
            lines.append(f"<b>Price:</b> €{price}")
        if size is not None:
            lines.append(f"<b>Size:</b> {size} m²")
        if doc.get("rooms") is not None:
            lines.append(f"<b>Rooms:</b> {doc['rooms']}")
        if availability:
            lines.append(f"<b>Availability:</b> {availability}")

        extra = []

        if source == "kamernet":
            if raw.get("furnishing"):
                extra.append(f"Furnishing: {raw['furnishing']}")
            if raw.get("type"):
                extra.append(f"Type: {raw['type']}")

        elif source == "pararius":
            if raw.get("interior"):
                extra.append(f"Interior: {raw['interior']}")
            if raw.get("landlord"):
                extra.append(f"Landlord: {raw['landlord']}")

        elif source == "roomspot":
            if raw.get("dwelling_type"):
                extra.append(f"Dwelling type: {raw['dwelling_type']}")
            if raw.get("floor"):
                extra.append(f"Floor: {raw['floor']}")
            if raw.get("rent_benefit") is not None:
                extra.append(f"Rent benefit: {'Yes' if raw['rent_benefit'] else 'No'}")
            if raw.get("housemates"):
                extra.append(f"Housemates: {raw['housemates']}")
            if raw.get("selection_model"):
                extra.append(f"Selection: {raw['selection_model']}")
            if raw.get("reactions") is not None:
                extra.append(f"Reactions: {raw['reactions']}")
            if raw.get("deadline"):
                extra.append(f"Deadline: {raw['deadline']}")

        if extra:
            lines.append("")
            lines.append("<b>Extra:</b>")
            for x in extra:
                lines.append(f"• {self.escape(str(x))}")

        if url:
            lines.append("")
            lines.append(f"<a href=\"{self.escape(url)}\">Open listing</a>")

        return "\n".join(lines)

    def escape(self, value):
        if value is None:
            return None
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def pretty_print_listing(self, data, is_new):
        status = "🆕 NEW LISTING" if is_new else "♻️ UPDATED"

        print("\n" + "=" * 60)
        print(f"{status}")
        print("=" * 60)

        print(f"🏠 {data.get('title') or data.get('street')}")
        print(f"📍 {data.get('city')} {data.get('district') or ''}")
        print(f"💰 €{data.get('price')}")
        print(f"📐 {data.get('size')} m² | 🛏 {data.get('rooms') or '-'}")

        if data.get("availability"):
            print(f"📅 {data.get('availability')}")

        print(f"🔗 {data.get('url')}")
        print(f"📦 source: {data.get('source')}")

        print("=" * 60 + "\n")