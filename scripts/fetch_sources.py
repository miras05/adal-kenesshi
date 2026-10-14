"""Скачивает официальные документы из data/sources.json (RU + KZ версии)
и сохраняет очищенный текст в data/corpus/<id>.<lang>.json.

Запуск:  python -m scripts.fetch_sources
"""
import json
import re
import sys
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.json"
CORPUS = ROOT / "data" / "corpus"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AdalQogamBot/1.0 (+student project IITU)"

DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*\s+\d{4})"
    r"|\b(\d{4}\s+жылғы\s+\d{1,2}\s+\w+)",
    re.IGNORECASE,
)
# Хвост страницы akorda.kz после основного текста (ленты новостей и т.п.)
TAIL_MARKERS = ["Вернуться назад", "Артқа қайту", "Back"]
TITLE_SUFFIX = re.compile(r"\s+—\s+(Официальный сайт|Қазақстан Республикасы Президентінің|Official website).*$")


def extract(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    title = TITLE_SUFFIX.sub("", title)

    kz_link = None
    for a in soup.find_all("a", href=True):
        if a.get_text(strip=True) == "Қаз" and "/kz/" in a["href"]:
            kz_link = a["href"]
            break

    body = soup.find("article") or soup.body
    for t in body(["script", "style", "nav", "header", "footer", "form"]):
        t.decompose()
    text = body.get_text("\n", strip=True)
    for m in TAIL_MARKERS:
        i = text.find(m)
        if i > 0:
            text = text[:i]
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    m = DATE_RE.search(text[:600])
    date = m.group(0) if m else ""
    return {"title": title, "text": text, "date": date, "kz_link": kz_link}


def fetch(client: httpx.Client, url: str) -> str:
    r = client.get(url, follow_redirects=True, timeout=40)
    r.raise_for_status()
    # Если документа нет на нужном языке, akorda.kz редиректит на главную
    if r.url.path.rstrip("/") in ("", "/ru", "/kz", "/en"):
        raise ValueError("редирект на главную — версии на этом языке нет")
    return r.text


def main(only: set[str] | None = None) -> None:
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    with httpx.Client(headers={"User-Agent": UA}) as client:
        for src in sources:
            if only and src["id"] not in only:
                continue
            urls = {"ru": src["url"]}
            for lang in ("ru", "kk"):
                url = urls.get(lang)
                if not url:
                    continue
                try:
                    page = extract(fetch(client, url))
                except Exception as e:  # сеть/404 — пропускаем, но сообщаем
                    print(f"  ✗ {src['id']}.{lang}: {e}")
                    continue
                if lang == "ru" and page["kz_link"]:
                    urls["kk"] = page["kz_link"].replace("://www.", "://")
                if len(page["text"]) < 300:
                    print(f"  ✗ {src['id']}.{lang}: слишком короткий текст ({len(page['text'])})")
                    continue
                doc = {
                    "id": src["id"],
                    "type": src["type"],
                    "lang": lang,
                    "title": page["title"],
                    "date": src.get("date") or page["date"],
                    "url": url,
                    "text": page["text"],
                }
                out = CORPUS / f"{src['id']}.{lang}.json"
                out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  ✓ {src['id']}.{lang}: {len(page['text']):>7} симв. | {doc['date'][:25]} | {page['title'][:60]}")
                time.sleep(0.5)  # бережно к серверу


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
