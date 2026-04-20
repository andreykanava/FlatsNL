from scrapy import signals


class FlatsDownloaderMiddleware:
    def __init__(self, proxy_list=None):
        self.proxies = self.parse_proxy_list(proxy_list or [])
        self.proxy_index = 0

    @classmethod
    def from_crawler(cls, crawler):
        s = cls(
            proxy_list=crawler.settings.getlist("REVERSE_PROXY_LIST"),
        )
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        return None

    def process_response(self, request, response, spider):
        if response.status == 200:
            return response

        retries = request.meta.get("proxy_retry_times", 0)
        max_retries = len(self.proxies)

        if retries >= max_retries or not self.proxies:
            spider.logger.warning(
                "Final failure for %s, status=%s, tried=%s/%s",
                request.url,
                response.status,
                retries,
                max_retries,
            )
            return response

        proxy = self.get_next_proxy()
        retry_req = request.copy()
        retry_req.dont_filter = True
        retry_req.meta["proxy"] = proxy
        retry_req.meta["proxy_retry_times"] = retries + 1

        spider.logger.warning(
            "Status %s for %s. Retry via %s (%s/%s)",
            response.status,
            request.url,
            proxy,
            retries + 1,
            max_retries,
        )
        return retry_req

    def process_exception(self, request, exception, spider):
        retries = request.meta.get("proxy_retry_times", 0)
        max_retries = len(self.proxies)

        if retries >= max_retries or not self.proxies:
            spider.logger.warning(
                "Exception for %s: %s. No proxies left.",
                request.url,
                exception,
            )
            return None

        proxy = self.get_next_proxy()
        retry_req = request.copy()
        retry_req.dont_filter = True
        retry_req.meta["proxy"] = proxy
        retry_req.meta["proxy_retry_times"] = retries + 1

        spider.logger.warning(
            "Exception for %s: %s. Retry via %s (%s/%s)",
            request.url,
            exception,
            proxy,
            retries + 1,
            max_retries,
        )
        return retry_req

    def get_next_proxy(self):
        proxy = self.proxies[self.proxy_index % len(self.proxies)]
        self.proxy_index += 1
        return proxy

    def parse_proxy_list(self, proxy_list):
        parsed = []

        for raw in proxy_list:
            raw = raw.strip()
            if not raw:
                continue

            parts = raw.split(":")
            if len(parts) == 4:
                host, port, username, password = parts
                parsed.append(f"http://{username}:{password}@{host}:{port}")
            elif len(parts) == 2:
                host, port = parts
                parsed.append(f"http://{host}:{port}")

        return parsed

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s", spider.name)