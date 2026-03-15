from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag


class LinkExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if not href:
            return
        absolute = urljoin(self.base_url, href)
        absolute, _ = urldefrag(absolute)
        self.links.append(absolute)


def extract_links(base_url: str, html: str):
    parser = LinkExtractor(base_url)
    parser.feed(html)
    return parser.links
