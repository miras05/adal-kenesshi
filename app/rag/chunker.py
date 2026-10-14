"""Нарезка документов на фрагменты (chunks) для поиска.

- Конституция режется по статьям: так бот может точно сослаться на «Статью N».
- Остальные документы режутся по абзацам в блоки ~CHUNK_SIZE символов
  с перекрытием в один абзац, чтобы не терять контекст на границе.
"""
import re
from dataclasses import asdict, dataclass

CHUNK_SIZE = 1200
MAX_ARTICLE = 2500

ARTICLE_RE = re.compile(r"^(?:Статья\s+(\d+)|(\d+)-бап)\s*$")
SECTION_RE = re.compile(r"^(?:Раздел\s+[IVXLІ]+|[IVXLІ]+\s+бөлім)\s*$")


@dataclass
class Chunk:
    id: str
    doc_id: str
    lang: str
    type: str
    title: str
    date: str
    url: str
    text: str
    article: str = ""   # номер статьи Конституции
    section: str = ""   # раздел Конституции

    def to_dict(self) -> dict:
        return asdict(self)


def _split_long(text: str, size: int) -> list[str]:
    """Делит текст по абзацам на части не длиннее size (с перекрытием в 1 абзац)."""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    parts, cur = [], []
    for p in paras:
        if cur and sum(len(x) for x in cur) + len(p) > size:
            parts.append("\n".join(cur))
            # перекрытие: последний абзац переносим, если он не слишком длинный
            cur = [cur[-1]] if len(cur[-1]) < size // 3 else []
        cur.append(p)
    if cur:
        parts.append("\n".join(cur))
    return parts


def chunk_constitution(doc: dict) -> list[Chunk]:
    lines = [l.strip() for l in doc["text"].split("\n") if l.strip()]
    chunks: list[Chunk] = []
    preamble: list[str] = []
    section, art_no, body = "", None, []
    pending_section = False

    def flush():
        if art_no is None:
            return
        text = "\n".join(body)
        for i, part in enumerate(_split_long(text, MAX_ARTICLE)):
            chunks.append(Chunk(
                id=f"{doc['id']}.{doc['lang']}.art{art_no}.{i}",
                doc_id=doc["id"], lang=doc["lang"], type=doc["type"],
                title=doc["title"], date=doc["date"], url=doc["url"],
                text=part, article=art_no, section=section,
            ))

    for line in lines:
        if SECTION_RE.match(line):
            flush()
            art_no, body = None, []
            section, pending_section = line, True
            continue
        if pending_section:  # строка после «Раздел N» — его название
            section = f"{section}. {line}"
            pending_section = False
            continue
        m = ARTICLE_RE.match(line)
        if m:
            flush()
            art_no, body = m.group(1) or m.group(2), []
            continue
        if art_no is None and not section:
            preamble.append(line)
        else:
            body.append(line)
    flush()

    if preamble:
        chunks.insert(0, Chunk(
            id=f"{doc['id']}.{doc['lang']}.preamble",
            doc_id=doc["id"], lang=doc["lang"], type=doc["type"],
            title=doc["title"], date=doc["date"], url=doc["url"],
            text="\n".join(preamble), article="преамбула" if doc["lang"] == "ru" else "кіріспе",
        ))
    return chunks


def chunk_generic(doc: dict) -> list[Chunk]:
    return [
        Chunk(
            id=f"{doc['id']}.{doc['lang']}.{i}",
            doc_id=doc["id"], lang=doc["lang"], type=doc["type"],
            title=doc["title"], date=doc["date"], url=doc["url"], text=part,
        )
        for i, part in enumerate(_split_long(doc["text"], CHUNK_SIZE))
    ]


def chunk_document(doc: dict) -> list[Chunk]:
    if doc["type"] == "constitution":
        return chunk_constitution(doc)
    return chunk_generic(doc)
