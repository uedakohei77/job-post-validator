# -*- coding: utf-8 -*-
"""
CLI for the category module.

  python3 -m src.categories refresh            # fetch everything since 2025-01-01 from Slack, rebuild index
  python3 -m src.categories refresh --since 2025-04-01   # or --days 365 for a rolling window
  python3 -m src.categories refresh --channel C0CURRENT --channel C08JG3E4LUF   # several channels
  python3 -m src.categories refresh --from-file a.json b.json   # offline, saved messages
  python3 -m src.categories list               # dropdown options with usage + variants
  python3 -m src.categories options            # dropdown options as JSON (for the posting form)
  python3 -m src.categories search 交通 --category 交通安全当番
  python3 -m src.categories template 教科書配布 # latest posting in a category, as a starting point
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from config import settings
from src.categories.parser import parse_messages
from src.categories.suggester import CategoryIndex, UNCATEGORIZED, build_index, latest_template, search


def _load_index(path):
    if not os.path.exists(path):
        print(f"No index at {path}. Run: python3 -m src.categories refresh")
        sys.exit(1)
    return CategoryIndex.load(path)


def resolve_window(args):
    """
    Returns (oldest_unix_ts, since_date_str). `--days N` (rolling window) wins if
    given; otherwise the fixed start date, from --since or CATEGORY_START_DATE.
    """
    if args.days:
        start = datetime.now(timezone.utc) - timedelta(days=args.days)
    else:
        try:
            start = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            print(f"[!] Invalid start date {args.since!r}; expected YYYY-MM-DD, e.g. 2025-01-01.")
            sys.exit(1)
    return start.timestamp(), start.date().isoformat()


def resolve_channels(args):
    """--channel flags win; otherwise CATEGORY_CHANNEL_IDS, then SLACK_CHANNEL_ID."""
    return args.channel or settings.CATEGORY_CHANNEL_IDS


def _collect_entries(args):
    """Returns (entries, total_messages) from saved files or from every configured channel."""
    entries, total = [], 0
    if args.from_file:
        for path in args.from_file:
            with open(path, "r", encoding="utf-8") as f:
                messages = json.load(f)
            label = os.path.splitext(os.path.basename(path))[0]
            print(f"Loaded {len(messages)} messages from {path}")
            entries.extend(parse_messages(messages, channel=label))
            total += len(messages)
        return entries, total

    # Imported lazily so offline use doesn't require Slack configuration.
    from src.auth import get_slack_token
    from src.slack_fetcher import fetch_slack_history_since

    channels = resolve_channels(args)
    if not channels:
        print("[!] No channel configured. Set CATEGORY_CHANNEL_IDS (or SLACK_CHANNEL_ID) in .env, "
              "or pass --channel C0123456789.")
        sys.exit(1)
    oldest, since = resolve_window(args)
    token = get_slack_token(force_reauth=args.force_reauth)
    for channel in channels:
        print(f"Fetching postings since {since} from channel {channel}...")
        messages = fetch_slack_history_since(channel, token, oldest)
        print(f"  {len(messages)} messages")
        if not messages:
            print(f"  [!] Nothing from {channel}: check the ID, that you are a member, "
                  "and that your token has the right history scope.")
        entries.extend(parse_messages(messages, channel=channel))
        total += len(messages)
    return entries, total


def cmd_refresh(args):
    entries, total = _collect_entries(args)
    if not total:
        print("Nothing fetched; leaving the existing index untouched.")
        sys.exit(1)
    since = "" if args.from_file else resolve_window(args)[1]
    index = build_index(entries, since=since)
    os.makedirs(os.path.dirname(args.index) or ".", exist_ok=True)
    index.save(args.index)

    suggested = sum(1 for p in index.postings if p["category_source"] == "suggested")
    none = sum(1 for p in index.postings if p["category_source"] == "none")
    print(
        f"Parsed {len(index.postings)} postings -> {len(index.categories)} suggested categories "
        f"({suggested} blank categories auto-suggested, {none} still uncategorized)."
    )
    print(f"Index written to {args.index}\n")
    _print_categories(index)


def _print_categories(index):
    for c in index.categories:
        extra = [f"{v} x{n}" for v, n in c.variants.items() if v != c.name]
        merged = f"  (merged: {', '.join(extra)})" if extra else ""
        print(f"  {c.name:<20} {c.posting_count:>3} postings  last {c.last_used[:10]}{merged}")
    if index.review_pairs:
        print("\nPossible duplicates for an admin to decide on:")
        for p in index.review_pairs:
            print(f"  {p['a']}  ~  {p['b']}   (similarity {p['similarity']})")
    none = [p for p in index.postings if p["category"] == UNCATEGORIZED]
    if none:
        print(f"\n{len(none)} postings have no category and no confident suggestion:")
        for p in none[:10]:
            print(f"  - {p['title']}")


def cmd_list(args):
    index = _load_index(args.index)
    since = f", postings since {index.since}" if index.since else ""
    print(f"Index generated {index.generated_at[:19]}{since}\n")
    _print_categories(index)


def cmd_options(args):
    index = _load_index(args.index)
    print(json.dumps(index.options, ensure_ascii=False, indent=2))


def _show(p):
    tag = "" if p["category_source"] == "explicit" else f" [{p['category_source']}]"
    print(f"{p['posted_at'][:10]}  [{p['category']}{tag}]  {p['title']}")


def cmd_search(args):
    index = _load_index(args.index)
    hits = search(index, " ".join(args.query), category=args.category, limit=args.limit)
    if not hits:
        print("No matching postings.")
        return
    for p in hits:
        _show(p)


def cmd_template(args):
    index = _load_index(args.index)
    p = latest_template(index, args.category)
    if not p:
        print(f"No postings in category '{args.category}'. Options: {', '.join(index.options)}")
        sys.exit(1)
    _show(p)
    print("-" * 80)
    print(p["body"])


def main():
    parser = argparse.ArgumentParser(description="Suggest and search volunteer-posting categories.")
    parser.add_argument("--index", default=settings.CATEGORY_INDEX_PATH, help="Path of the index JSON.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("refresh", help="Fetch postings and rebuild the category index.")
    p.add_argument("--since", default=settings.CATEGORY_START_DATE,
                   help="Fetch postings from this date (YYYY-MM-DD) to now. Default: CATEGORY_START_DATE.")
    p.add_argument("--days", type=int, help="Rolling window of the last N days instead of --since.")
    p.add_argument("--channel", action="append",
                   help="Slack channel ID to scan; repeat for several. Overrides CATEGORY_CHANNEL_IDS.")
    p.add_argument("--from-file", nargs="+",
                   help="Read Slack messages from one or more JSON files instead of calling Slack.")
    p.add_argument("--force-reauth", action="store_true")
    p.set_defaults(func=cmd_refresh)

    sub.add_parser("list", help="Show categories.").set_defaults(func=cmd_list)
    sub.add_parser("options", help="Dropdown options as JSON.").set_defaults(func=cmd_options)

    p = sub.add_parser("search", help="Search past postings.")
    p.add_argument("query", nargs="*", help="Keywords; all must match.")
    p.add_argument("--category")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("template", help="Latest posting in a category, to reuse for a new post.")
    p.add_argument("category")
    p.set_defaults(func=cmd_template)

    args = parser.parse_args()
    args.func(args)
