import logging
import re
import urllib.parse
from typing import Any, Optional
import httpx
from lxml import html

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT_LANGUAGE = "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7"
DEFAULT_TIMEOUT = 15.0


class PromScraper:
    """HTTP client and HTML parser for Prom.ua search results."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Language": accept_language,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Search Prom.ua for a given query and extract product cards."""
        encoded_query = urllib.parse.quote(query.strip())
        search_url = f"https://prom.ua/ua/search?search_term={encoded_query}"

        try:
            with httpx.Client(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = client.get(search_url)

            if response.status_code != 200:
                logger.warning(
                    f"Prom.ua returned status {response.status_code} for query '{query}'"
                )
                return []

            return self._parse_html(response.text, max_results=max_results)

        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning(f"Network error while scraping Prom.ua query '{query}': {exc}")
            return []
        except Exception as exc:
            logger.warning(f"Unexpected error while scraping Prom.ua query '{query}': {exc}")
            return []

    def _parse_html(self, html_content: str, max_results: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        try:
            tree = html.fromstring(html_content)
        except Exception as exc:
            logger.warning(f"Failed to parse HTML from Prom.ua: {exc}")
            return results

        blocks = tree.xpath('//*[@data-qaid="product_block"]')

        for block in blocks:
            if len(results) >= max_results:
                break

            # 1. Product title
            name_nodes = block.xpath('.//*[@data-qaid="product_name"]//text()')
            if not name_nodes:
                name_nodes = block.xpath('.//*[@data-qaid="product_link"]//text()')
            title = "".join(name_nodes).strip()
            if not title:
                continue

            # 2. Product price
            price_nodes = block.xpath('.//*[@data-qaid="product_price"]//text()')
            raw_price = "".join(price_nodes)
            price = self._clean_price(raw_price)
            if price is None:
                continue

            # 3. Seller name
            company_nodes = block.xpath('.//*[@data-qaid="company_name"]//text()')
            seller_name = "".join(company_nodes).strip() or None

            # 4. Stock presence
            presence_nodes = block.xpath('.//*[@data-qaid="product_presence"]//text()')
            presence_text = "".join(presence_nodes).lower()
            if presence_text:
                is_in_stock = (
                    "наявності" in presence_text or "відправки" in presence_text
                ) and "немає" not in presence_text
            else:
                is_in_stock = True

            # 5. Product link
            links = block.xpath('.//*[@data-qaid="product_link"]/@href')
            if not links:
                links = block.xpath('.//a[contains(@href, "/p")]/@href')
            if not links:
                links = block.xpath('.//a[contains(@href, "/m")]/@href')
            if not links:
                continue

            raw_link = links[0].strip()
            full_url = urllib.parse.urljoin("https://prom.ua", raw_link)

            # 6. Product image
            imgs = block.xpath('.//img/@src') or block.xpath('.//img/@data-src')
            image_url = imgs[0].strip() if imgs else None

            # 7. External ID
            external_id = self._extract_external_id(full_url, block)

            results.append(
                {
                    "source": "prom.ua",
                    "external_id": external_id,
                    "title": title,
                    "price": price,
                    "seller_name": seller_name,
                    "url": full_url,
                    "image_url": image_url,
                    "is_in_stock": is_in_stock,
                }
            )

        return results

    @staticmethod
    def _clean_price(raw_text: str) -> Optional[float]:
        cleaned = (
            raw_text.replace("\xa0", " ")
            .replace("₴", "")
            .replace("грн", "")
            .replace(" ", "")
            .replace(",", ".")
            .strip()
        )
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_external_id(url: str, block: Any) -> Optional[str]:
        # 1. From data attributes
        block_id = block.get("data-product-id") or block.get("data-qaid-product-id")
        if block_id and block_id.strip():
            return block_id.strip()

        # 2. From URL query param (?p=...)
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "p" in qs and qs["p"]:
            return qs["p"][0].strip()
        if "portal_product_id" in qs and qs["portal_product_id"]:
            return qs["portal_product_id"][0].strip()

        # 3. From URL path
        match = re.search(r"-p(\d+)", parsed.path)
        if match:
            return match.group(1)
        match = re.search(r"/p(\d+)", parsed.path)
        if match:
            return match.group(1)
        match = re.search(r"/m-?(\d+)", parsed.path)
        if match:
            return match.group(1)

        return None
