"""Гибридный поиск: векторный (смысловой) + BM25 (по ключевым словам).

Почему гибрид:
- векторный поиск находит ответ, даже если вопрос задан другими словами
  или на другом языке (вопрос на казахском — документ на русском);
- BM25 надёжно ловит точные термины: «Таза Қазақстан», «статья 33», «Курултай».
Результаты объединяются методом Reciprocal Rank Fusion (RRF).
"""
import re
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi

from app import config

RRF_K = 60          # стандартная константа RRF
CANDIDATES = 40     # сколько кандидатов берём из каждого метода
MAX_PER_DOC = 3     # не больше N фрагментов из одного документа (разнообразие)
CONSTITUTION_EXTRA = 3
CONSTITUTION_MIN_DENSE = 0.78  # мягче общего порога: статьи длинные, их вектор «размыт»

WORD_RE = re.compile(r"\w+", re.UNICODE)
STOP = set("и в во не на что как это по к с со из за от для о об а но же ли бы у до он она они "
           "такое такой какой какие какая каком где когда кто чем говорит говорится сказано означает "
           "закре конст стать "  # «закреплён ли в Конституции, статья» — служебные для поиска
           "мен және бен пен да де ма ме ба бе па пе бұл осы сол не қалай деген дегені кім қандай "
           "бекіт бап".split())
KK_LETTERS = set("әғқңөұүһі")
QUOTED_RE = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”")
# казахские названия, которые часто пишут и в русском тексте
KK_NAMES = re.compile(r"\b(таза|қазақ\w*|қоғам\w*|құрылтай\w*|халық|кеңес\w*|толық|адал|азамат|әділетті)\b")
# Характерные казахские слова. Сравниваем после «упрощения» букв (қ→к, ұ→у, і→и…),
# чтобы распознать казахский, набранный на русской раскладке или латиницей.
KK_SIMPLIFY = str.maketrans("әғқңөұүһі", "агкноуухи")
KK_WORDS = {
    # кириллица (в упрощённом виде). Только слова, которых нет в русском
    # («не», «бар», «Ким», «казак», частицы «ма/ба» исключены).
    "нени", "калай", "кандай", "канша", "неше", "кашан", "кайда", "неге", "кимге", "кимдер",
    "деген", "дегенимиз", "дегени", "дейди", "туралы", "бойынша", "ушин", "жане", "жок",
    "айтыныз", "тусиндириниз", "болады", "турады", "сайланады", "кабылданады", "курылады",
    "белгиленген", "бекитилген", "айтылган", "жазылган", "мемлекет", "тили", "кандай",
    # латиница
    "qansha", "qalai", "qandai", "neshe", "qashan", "turady", "bolady", "degenimiz", "degen",
    "turaly", "boiynsha", "ushin", "sailanady", "memleket",
}


def detect_lang(text: str) -> str:
    """Казахский — если есть казахские буквы или служебные слова вне названий
    («Таза Қазақстан» в русском вопросе не делает его казахским)."""
    t = KK_NAMES.sub(" ", QUOTED_RE.sub(" ", text.lower()))
    if any(ch in KK_LETTERS for ch in t):
        return "kk"
    words = WORD_RE.findall(t.translate(KK_SIMPLIFY))
    return "kk" if any(w in KK_WORDS for w in words) else "ru"


def tokenize(text: str) -> list[str]:
    """Простой «стеммер»: обрезаем слова до 5 букв («порядок», «порядка» → «поряд»).
    Для русского и казахского (богатая морфология) это даёт заметный прирост качества BM25."""
    stems = (w[:5] for w in WORD_RE.findall(text.lower()) if w not in STOP and len(w) > 1)
    return [s for s in stems if s not in STOP]


def bm25_terms(text: str) -> list[str]:
    """Слова + биграммы (пары соседних слов). Биграммы различают устойчивые
    формулы: «Закон и Порядок» (закон_поряд) ≠ «в порядке, установленном законом»."""
    words = tokenize(text)
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


@dataclass
class Hit:
    chunk: dict
    dense: float          # косинусная близость (0..1) — для порога «ответа нет»
    score: float = 0.0    # итоговый RRF-балл
    via: list[str] = field(default_factory=list)


class Retriever:
    def __init__(self, chunks: list[dict], embeddings: np.ndarray, embed_query):
        self.chunks = chunks
        self.emb = embeddings
        self.embed_query = embed_query
        from app.rag.index import chunk_header

        self.bm25 = BM25Okapi([bm25_terms(f"{chunk_header(c)} {c['text']}") for c in chunks])
        self.const_idx = np.array([i for i, c in enumerate(chunks) if c["type"] == "constitution"])
        # быстрый доступ к той же статье Конституции/закона на другом языке
        self.by_article = {(c["doc_id"], c["lang"], c["article"], c["id"].rsplit(".", 1)[-1]): i
                           for i, c in enumerate(chunks) if c.get("article")}

    def search(self, query: str, k: int = config.TOP_K, lang: str | None = None) -> list[Hit]:
        lang = lang or detect_lang(query)
        qv = self.embed_query(query)
        dense = self.emb @ qv

        dense_top = np.argsort(-dense)[:CANDIDATES]
        bm = self.bm25.get_scores(bm25_terms(query))
        bm_top = [i for i in np.argsort(-bm)[:CANDIDATES] if bm[i] > 0]

        fused: dict[int, Hit] = {}
        for method, ranking in (("vector", dense_top), ("bm25", bm_top)):
            for rank, i in enumerate(ranking):
                i = int(i)
                h = fused.setdefault(i, Hit(self.chunks[i], float(dense[i])))
                h.score += 1.0 / (RRF_K + rank + 1)
                h.via.append(method)

        hits, per_doc, seen = [], {}, set()
        for i, h in sorted(fused.items(), key=lambda x: -x[1].score):
            i = self._same_article_in_lang(i, lang)
            c = self.chunks[i]
            key = (c["doc_id"], c["article"] or c["id"])
            if key in seen or per_doc.get(c["doc_id"], 0) >= MAX_PER_DOC:
                continue
            seen.add(key)
            per_doc[c["doc_id"]] = per_doc.get(c["doc_id"], 0) + 1
            hits.append(Hit(c, max(h.dense, float(dense[i])), h.score, h.via))
            if len(hits) >= k:
                break

        hits += self._constitution_check(dense, bm, lang, seen)
        return hits

    def _same_article_in_lang(self, i: int, lang: str) -> int:
        """Статью Конституции или закона показываем на языке пользователя."""
        c = self.chunks[i]
        if not c.get("article") or c["lang"] == lang:
            return i
        other = self.by_article.get((c["doc_id"], lang, self._kk_ru_article(c["article"], lang), c["id"].rsplit(".", 1)[-1]))
        return other if other is not None else i

    @staticmethod
    def _kk_ru_article(article: str, lang: str) -> str:
        if article in ("преамбула", "кіріспе"):
            return "преамбула" if lang == "ru" else "кіріспе"
        return article

    def _constitution_check(self, dense: np.ndarray, bm: np.ndarray, lang: str, seen: set) -> list[Hit]:
        """Требование конкурса: если понятие закреплено в Конституции 2026,
        бот обязан это указать. Поэтому отдельно ищем лучшие статьи Конституции
        (тем же гибридом: смысл + ключевые слова) и добавляем их в контекст."""
        if not len(self.const_idx):
            return []
        ci = self.const_idx
        rrf = np.zeros(len(ci))
        for ranking in (np.argsort(-dense[ci]), np.argsort(-bm[ci])):
            rrf[ranking] += 1.0 / (RRF_K + np.arange(1, len(ci) + 1))
        extra = []
        for pos in np.argsort(-rrf):
            i = int(ci[pos])
            if dense[i] < CONSTITUTION_MIN_DENSE and bm[i] <= 0:
                continue
            j = self._same_article_in_lang(i, lang)
            c = self.chunks[j]
            key = (c["doc_id"], c["article"] or c["id"])
            if key in seen:
                continue
            seen.add(key)
            extra.append(Hit(c, float(dense[i]), 0.0, ["constitution"]))
            if len(extra) >= CONSTITUTION_EXTRA:
                break
        return extra
