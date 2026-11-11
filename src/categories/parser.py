# -*- coding: utf-8 -*-
"""
Parses Slack volunteer-posting messages into individual job entries.

One Slack message can contain several jobs (each starting with 業務名称), and the
same job is often repeated once per date. Each job carries an optional
``カテゴリ:`` field that is currently free text.
"""
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

# Field labels used in postings. Used both to find values and to know where a
# value ends (postings are frequently flattened onto one line).
LABELS = [
    "業務名称", "カテゴリ", "対象学校・学年", "業務開始日時", "業務終了日時",
    "申込開始日時", "申込終了日時", "対象", "募集人数", "貢献点",
    "選出方法", "業務詳細", "集合場所",
]
_LABEL_ALT = "|".join(sorted((re.escape(l) for l in LABELS), key=len, reverse=True))
_SEP = r"\s*[:：]\s*"

# Start of each job block.
_JOB_SPLIT = re.compile(r"(?=業務名称" + _SEP + ")")
# Footer / divider lines that follow the last job in a message.
_FOOTER = re.compile(r"[ー_―━＿\-]{5,}|＊補習校ポータル|＊応募はこちら")
# Trailing "26年04月04日,11日" style date tokens that Slack titles often carry.
_TITLE_DATE_TAIL = re.compile(r"\s*\d{2,4}年\s*\d{1,2}月\s*\d{1,2}日(?:\s*[,、]\s*\d{1,2}日)*\s*(?:\([^)]*\)|（[^）]*）)?\s*$")

MAX_CATEGORY_LEN = 40  # longer than this means we mis-parsed, not a real category


@dataclass
class JobEntry:
    message_ts: str          # Slack message ts (unique id within channel)
    posted_at: str           # ISO8601 UTC
    title: str               # 業務名称 without trailing dates
    category_raw: str        # カテゴリ exactly as typed ("" if absent)
    start: str               # 業務開始日時 (raw text)
    points: str              # 貢献点 (raw text)
    headcount: str           # 募集人数 (raw text)
    audience: str            # 対象 (raw text)
    body: str                # the full job block, reusable as a template

    def to_dict(self):
        return asdict(self)


def _field(block, label):
    """
    Returns the single-line value of `label` in `block`. A value ends at the next
    known label (posts are often flattened onto one line) or at the line break
    (real posts use unlisted labels such as 場所: on the following line).
    """
    m = re.search(
        re.escape(label) + r"[ \t　]*[:：][ \t　]*(.*?)(?=\s(?:" + _LABEL_ALT + r")" + _SEP + r"|$)",
        block,
        re.S,
    )
    if not m:
        return ""
    return m.group(1).split("\n", 1)[0].strip()


def _valid_category(value):
    """A "category" that runs on is a parsing miss (label with no clear end)."""
    return value if len(value) <= MAX_CATEGORY_LEN else ""


def _clean_title(title):
    return _TITLE_DATE_TAIL.sub("", title).strip()


def ts_to_iso(ts):
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def parse_message(message):
    """
    Parses one Slack message dict ({"ts":..., "text":...}) into JobEntry list.
    Returns [] when the message is not a volunteer posting.
    """
    text = (message.get("text") or "").strip()
    ts = str(message.get("ts", ""))
    if "業務名称" not in text:
        return _parse_unlabelled(text, ts)

    entries = []
    for block in _JOB_SPLIT.split(text):
        block = block.strip()
        if not block.startswith("業務名称"):
            continue  # preamble such as "@channel 【事務局からのサポーター募集】"
        footer = _FOOTER.search(block)
        if footer:
            block = block[: footer.start()].strip()

        category = _valid_category(_field(block, "カテゴリ"))

        entries.append(JobEntry(
            message_ts=ts,
            posted_at=ts_to_iso(ts) if ts else "",
            title=_clean_title(_field(block, "業務名称")),
            category_raw=category,
            start=_field(block, "業務開始日時"),
            points=_field(block, "貢献点"),
            headcount=_field(block, "募集人数"),
            audience=_field(block, "対象"),
            body=block,
        ))
    return entries


_LOOKS_LIKE_POST = re.compile(r"貢献点|募集人数")
_DECOR = re.compile(r"@(?:channel|here)|:[a-z0-9_+\-]+:|[━─―=＿_\-]{3,}|ー{3,}")


def _parse_unlabelled(text, ts):
    """
    Older / ad-hoc postings have no 業務名称 label, only a heading and fields such
    as 募集人数 / 貢献点. Treat the whole message as one job, titled by its heading.
    """
    if not _LOOKS_LIKE_POST.search(text):
        return []
    first_label = re.search(_LABEL_ALT + _SEP, text)
    preamble = text[: first_label.start()] if first_label else text
    lines = [re.sub(r"\s+", " ", _DECOR.sub(" ", ln)).strip() for ln in preamble.splitlines()]
    # Skip empty lines and tag-only lines such as 【再告知】 (re-announcement).
    heading = next((ln for ln in lines if ln and not re.fullmatch(r"【[^】]*】", ln)), "")
    if not heading:  # single flattened line
        heading = re.sub(r"\s+", " ", _DECOR.sub(" ", preamble)).strip()
    heading = heading[:80]
    return [JobEntry(
        message_ts=ts,
        posted_at=ts_to_iso(ts) if ts else "",
        title=heading,
        category_raw=_valid_category(_field(text, "カテゴリ")),
        start=_field(text, "業務開始日時"),
        points=_field(text, "貢献点"),
        headcount=_field(text, "募集人数"),
        audience=_field(text, "対象"),
        body=text,
    )]


_IGNORED_SUBTYPES = {
    "channel_join", "channel_leave", "channel_topic", "channel_purpose",
    "channel_name", "channel_archive", "channel_unarchive", "pinned_item",
}


def parse_messages(messages):
    """Parses many messages, skipping Slack system messages."""
    entries = []
    for msg in messages:
        if msg.get("subtype") in _IGNORED_SUBTYPES:
            continue
        entries.extend(parse_message(msg))
    return entries
