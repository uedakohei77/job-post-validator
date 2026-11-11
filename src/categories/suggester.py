# -*- coding: utf-8 -*-
"""
Builds a de-duplicated category list from past volunteer postings.

Today ``カテゴリ`` is free text, so "交通安全当番", "交通安全 当番" and
"交通安全当番（下校時）" are all "different". This module:

  1. normalizes each raw category into a comparison key,
  2. auto-merges keys that are near-identical (typos, spacing, qualifiers),
  3. flags borderline pairs for an admin to decide on,
  4. suggests a category for jobs that have none,
  5. exposes search / "use as template" helpers over the past postings.

It is deliberately offline and deterministic (no LLM calls): the output is a
suggestion an admin reviews once, and then freezes into the dropdown.
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from difflib import SequenceMatcher

AUTO_MERGE_THRESHOLD = 0.80   # >= this: treated as the same category
REVIEW_THRESHOLD = 0.60       # [review, merge): shown to admin as "maybe the same"
TITLE_MATCH_THRESHOLD = 0.60  # min similarity to borrow a category from a similar title

UNCATEGORIZED = "未分類"

_PAREN = re.compile(r"\([^)]*\)")
_SEPARATORS = re.compile(r"[\s・/,、.。:;_\-\[\]【】「」『』]")


def normalize(text):
    """
    Comparison key: NFKC (full/half-width), lower-case, qualifiers in parentheses
    dropped, spaces/separators removed. The long-vowel mark 'ー' is preserved.
    """
    t = unicodedata.normalize("NFKC", text or "").casefold()
    stripped = _SEPARATORS.sub("", _PAREN.sub("", t))
    # If the whole value was parenthesised, keep it rather than returning "".
    return stripped or _SEPARATORS.sub("", t)


def _ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class Category:
    name: str                          # canonical label for the dropdown
    posting_count: int                 # distinct postings that used it
    first_used: str
    last_used: str
    variants: dict = field(default_factory=dict)   # raw spelling -> postings
    examples: list = field(default_factory=list)   # most recent [{title, posted_at, message_ts}]


@dataclass
class CategoryIndex:
    generated_at: str
    window_days: int
    categories: list            # list[Category] (dropdown order: most used first)
    review_pairs: list          # [{a, b, similarity}] borderline duplicates
    postings: list              # every job entry + resolved category info

    @property
    def options(self):
        """Dropdown values."""
        return [c.name for c in self.categories]

    def to_dict(self):
        d = asdict(self)
        d["options"] = self.options
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(
            generated_at=d["generated_at"],
            window_days=d["window_days"],
            categories=[Category(**c) for c in d["categories"]],
            review_pairs=d.get("review_pairs", []),
            postings=d["postings"],
        )

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def resolve(self, raw):
        """
        Maps any free-text category (e.g. from a legacy posting) onto a dropdown
        option, or None if nothing is close enough.
        """
        key = normalize(raw)
        if not key:
            return None
        best, best_score = None, 0.0
        for c in self.categories:
            score = 1.0 if key == normalize(c.name) or any(
                key == normalize(v) for v in c.variants
            ) else _ratio(key, normalize(c.name))
            if score > best_score:
                best, best_score = c.name, score
        return best if best_score >= AUTO_MERGE_THRESHOLD else None


def _dedupe_postings(entries):
    """
    One "posting" = one (message, job title). A job repeated once per date inside
    one message must not inflate the counts.
    """
    seen, unique = set(), []
    for e in entries:
        k = (e["message_ts"], normalize(e["title"]), normalize(e["category_raw"]))
        if k not in seen:
            seen.add(k)
            unique.append(e)
    return unique


def build_index(entries, window_days=365, now=None):
    """
    Builds the CategoryIndex from parsed JobEntry objects (or their dicts).
    """
    rows = [e if isinstance(e, dict) else e.to_dict() for e in entries]
    rows = _dedupe_postings(rows)
    now = now or datetime.now(timezone.utc)

    # 1. Group explicit categories by normalized key.
    by_key = defaultdict(list)
    for r in rows:
        key = normalize(r["category_raw"])
        if key:
            by_key[key].append(r)

    # 2. Greedy merge, most-used keys first so they become the canonical ones.
    ordered = sorted(by_key, key=lambda k: (-len(by_key[k]), k))
    clusters = []        # each: {"key": canonical_key, "rows": [...]}
    review = {}          # (a, b) -> similarity
    for key in ordered:
        target, target_score = None, 0.0
        for cl in clusters:
            s = _ratio(key, cl["key"])
            if s > target_score:
                target, target_score = cl, s
        if target and target_score >= AUTO_MERGE_THRESHOLD:
            target["rows"].extend(by_key[key])
        else:
            clusters.append({"key": key, "rows": list(by_key[key])})
            if target and target_score >= REVIEW_THRESHOLD:
                review[(target["key"], key)] = target_score

    # 3. Materialize categories.
    categories = []
    key_to_name = {}
    for cl in clusters:
        raws = Counter(r["category_raw"].strip() for r in cl["rows"])
        newest = max(r["posted_at"] for r in cl["rows"])
        # Most used spelling wins; ties prefer the shorter (usually space-free) one.
        name = sorted(raws, key=lambda v: (-raws[v], len(v), v))[0]
        recent = sorted(cl["rows"], key=lambda r: r["posted_at"], reverse=True)
        categories.append(Category(
            name=name,
            posting_count=len(cl["rows"]),
            first_used=min(r["posted_at"] for r in cl["rows"]),
            last_used=newest,
            variants=dict(raws.most_common()),
            examples=[
                {"title": r["title"], "posted_at": r["posted_at"], "message_ts": r["message_ts"]}
                for r in recent[:3]
            ],
        ))
        key_to_name[cl["key"]] = name
    categories.sort(key=lambda c: (-c.posting_count, c.name))

    review_pairs = [
        {"a": key_to_name[a], "b": key_to_name.get(b, b), "similarity": round(s, 2)}
        for (a, b), s in sorted(review.items(), key=lambda kv: -kv[1])
    ]

    # 4. Resolve each posting's category; suggest one where it was left blank.
    index = CategoryIndex(
        generated_at=now.isoformat(),
        window_days=window_days,
        categories=categories,
        review_pairs=review_pairs,
        postings=[],
    )
    explicit_titles = [(normalize(r["title"]), r) for r in rows if r["category_raw"].strip()]
    for r in rows:
        out = dict(r)
        if r["category_raw"].strip():
            out["category"] = index.resolve(r["category_raw"]) or r["category_raw"].strip()
            out["category_source"] = "explicit"
        else:
            suggestion = _suggest_for_title(r["title"], index, explicit_titles)
            out["category"] = suggestion or UNCATEGORIZED
            out["category_source"] = "suggested" if suggestion else "none"
        index.postings.append(out)
    index.postings.sort(key=lambda p: p["posted_at"], reverse=True)
    return index


def _suggest_for_title(title, index, explicit_titles):
    """
    Category for a posting that has none:
      1. a known category name appears inside the title (longest match wins), else
      2. the category of the most similar already-categorized title.
    """
    t = normalize(title)
    if not t:
        return None
    hits = [c.name for c in index.categories if len(normalize(c.name)) >= 2 and normalize(c.name) in t]
    if hits:
        return max(hits, key=lambda n: len(normalize(n)))
    best, best_score = None, 0.0
    for other_title, r in explicit_titles:
        s = _ratio(t, other_title)
        if s > best_score:
            best, best_score = r, s
    if best and best_score >= TITLE_MATCH_THRESHOLD:
        return index.resolve(best["category_raw"])
    return None


# ---------------------------------------------------------------- search helpers

def _fold(text):
    """Search folding: width/case-insensitive, whitespace-insensitive, keeps ( ) text."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or "").casefold())


def _haystack(p):
    return _fold(" ".join([p["title"], p["category"], p["audience"], p["body"]]))


def search(index, query="", category=None, limit=20):
    """
    Newest-first postings matching ALL whitespace-separated terms in `query`
    (width/case-insensitive), optionally restricted to one dropdown category.
    """
    terms = [_fold(t) for t in (query or "").split() if _fold(t)]
    hits = []
    for p in index.postings:
        if category and p["category"] != category:
            continue
        hay = _haystack(p)
        if all(t in hay for t in terms):
            hits.append(p)
    return hits[:limit]


def latest_template(index, category):
    """Most recent posting in `category`, to use as the starting point for a new post."""
    hits = search(index, category=category, limit=1)
    return hits[0] if hits else None
