from html import unescape
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


class TextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "footer",
        "li",
        "main",
        "nav",
        "p",
        "section",
        "tr",
    }
    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        cleaned = " ".join(unescape(data).split())
        if cleaned:
            self._parts.append(cleaned)
            self._parts.append(" ")

    def text(self):
        collapsed = "".join(self._parts)
        lines = [" ".join(line.split()) for line in collapsed.splitlines()]
        return "\n".join(line for line in lines if line).strip()


def extract_text(html: str):
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()
