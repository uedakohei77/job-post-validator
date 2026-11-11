# -*- coding: utf-8 -*-
from unittest import mock

from src.categories import build_index, latest_template, normalize, parse_messages, search
from src.categories.parser import parse_message
from src.categories.suggester import CategoryIndex, UNCATEGORIZED
from src import slack_fetcher


def msg(ts, text, **extra):
    return {"ts": f"{1772323200 + ts}.000100", "text": text, **extra}


def job(title, category=None, extra="募集人数: １２人 貢献点：各1.0点", colon=":"):
    cat = f" カテゴリ{colon}{category}" if category is not None else ""
    return f"業務名称: {title}{cat} 業務開始日時：2026年04月04日（土）午前09時00分 {extra}"


HEADER = "@channel 【事務局からのサポーター募集】 "
FOOTER = " ーーーーーーーーーーーーーーーーーーーーー ＊補習校ポータルリンク(応募はこちらから) https://app.sfjs.org/"

MESSAGES = [
    msg(1, HEADER + job("SJ幼小部 ランチ当番 26年04月04日", "ランチ当番") + FOOTER),
    msg(2, HEADER + job("SJ幼小部 ランチ当番 26年05月02日", "ランチ 当番") + FOOTER),
    msg(3, HEADER + job("SJ中高部 ランチ当番 26年06月06日", "ランチ当番（幼小部）", colon="：") + FOOTER),
    # same job repeated once per date inside ONE message
    msg(4, HEADER + " ".join(
        job(f"SJ 中高部 交通安全当番（下校時） 26年04月{d}日", "交通安全当番") for d in (4, 11, 18, 25)
    ) + FOOTER),
    msg(5, HEADER + job("SJ 小学部 交通安全当番", "交通安全 当番") + FOOTER),
    msg(6, HEADER + job("SJ幼小部 教科書配布", "教科書配布") + " " + job("SJ中高部 教科書配付", "教科書配付") + FOOTER),
    msg(7, HEADER + job("春のイベント準備", "イベント準備") + FOOTER),
    msg(8, HEADER + job("春のイベント運営", "イベント運営") + FOOTER),
    # blank category: should be suggested from the title
    msg(9, HEADER + job("SJ幼小部 ランチ当番 26年09月05日") + FOOTER),
    # old-style post: no 業務名称 at all
    msg(10, "@channel ━━━━━━━━━━ :four_leaf_clover: スポーツサックの仕分けボランティア募集 ━━━━━━━━━━ 募集人数：1人 貢献点：1点"),
    # noise
    msg(11, "ありがとうございました！"),
    msg(12, "has joined the channel", subtype="channel_join"),
]


def build():
    return build_index(parse_messages(MESSAGES), since="2025-01-01")


# ------------------------------------------------------------------ parsing

def test_normalize_collapses_spacing_width_and_qualifiers():
    assert normalize("ランチ 当番") == normalize("ランチ当番") == normalize("ランチ当番（幼小部）")
    assert normalize("ＡＢＣ") == normalize("abc")
    assert "ー" in normalize("レクリエーション")  # long-vowel mark must survive


def test_parse_splits_jobs_and_cleans_titles():
    entries = parse_message(MESSAGES[5])
    assert [e.title for e in entries] == ["SJ幼小部 教科書配布", "SJ中高部 教科書配付"]
    assert [e.category_raw for e in entries] == ["教科書配布", "教科書配付"]
    assert entries[0].points == "各1.0点"
    assert "ポータル" not in entries[1].body  # footer cut off


def test_parse_handles_fullwidth_colon_and_missing_category():
    assert parse_message(MESSAGES[2])[0].category_raw == "ランチ当番（幼小部）"
    assert parse_message(MESSAGES[8])[0].category_raw == ""


def test_unlabelled_post_is_indexed_by_heading():
    (e,) = parse_message(MESSAGES[9])
    assert e.title == "スポーツサックの仕分けボランティア募集"


def test_noise_and_system_messages_ignored():
    assert parse_messages([MESSAGES[10], MESSAGES[11]]) == []


# ------------------------------------------------------------------ suggestion

def test_spelling_variants_merge_into_one_category():
    idx = build()
    lunch = next(c for c in idx.categories if c.name == "ランチ当番")
    assert lunch.posting_count == 3
    assert set(lunch.variants) == {"ランチ当番", "ランチ 当番", "ランチ当番（幼小部）"}
    # 配付 / 配布 typo merged
    assert sum(1 for c in idx.categories if "教科書" in c.name) == 1


def test_repeated_dates_in_one_message_count_once():
    idx = build()
    traffic = next(c for c in idx.categories if c.name == "交通安全当番")
    assert traffic.posting_count == 2  # message 4 (x4 dates) + message 5


def test_dropdown_options_are_unique_and_ordered_by_use():
    idx = build()
    assert idx.options[:2] == ["ランチ当番", "交通安全当番"]   # 3 and 2 postings
    assert len(set(idx.options)) == len(idx.options) == 5      # no duplicates


def test_borderline_pairs_flagged_not_merged():
    idx = build()
    assert "イベント準備" in idx.options and "イベント運営" in idx.options
    assert any({p["a"], p["b"]} == {"イベント準備", "イベント運営"} for p in idx.review_pairs)


def test_blank_category_suggested_from_title():
    idx = build()
    p = next(p for p in idx.postings if p["message_ts"] == MESSAGES[8]["ts"])
    assert p["category"] == "ランチ当番" and p["category_source"] == "suggested"


def test_unmatched_blank_category_is_uncategorized():
    idx = build()
    p = next(p for p in idx.postings if "スポーツサック" in p["title"])
    assert p["category"] == UNCATEGORIZED and p["category_source"] == "none"


def test_resolve_maps_legacy_free_text_onto_options():
    idx = build()
    assert idx.resolve("ランチ  当番") == "ランチ当番"
    assert idx.resolve("全く別のもの") is None


# ------------------------------------------------------------------ search / template

def test_search_matches_parenthetical_text_and_fullwidth_digits():
    idx = build()
    assert any("交通安全" in p["title"] for p in search(idx, "下校"))      # text inside （ ）
    textbook = next(n for n in idx.options if "教科書" in n)
    assert search(idx, "12人", category=textbook)                          # body has １２人
    assert search(idx, "ランチ 当番", category="ランチ当番")               # multi-term, spacing-insensitive
    assert search(idx, "存在しない語") == []


def test_latest_template_returns_newest_posting():
    idx = build()
    t = latest_template(idx, "ランチ当番")
    assert t["message_ts"] == MESSAGES[8]["ts"]  # the suggested one is newest
    explicit = [p for p in search(idx, category="ランチ当番") if p["category_source"] == "explicit"]
    assert explicit[0]["message_ts"] == MESSAGES[2]["ts"]


def test_index_roundtrip(tmp_path):
    idx = build()
    path = tmp_path / "idx.json"
    idx.save(path)
    again = CategoryIndex.load(path)
    assert again.options == idx.options and len(again.postings) == len(idx.postings)


# ------------------------------------------------------------------ slack pagination

def _resp(payload, status=200, headers=None):
    r = mock.Mock(status_code=status, headers=headers or {})
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def test_fetch_since_paginates_and_retries_on_429():
    pages = [
        _resp({"ok": True, "messages": [{"ts": "3"}, {"ts": "2"}], "has_more": True,
               "response_metadata": {"next_cursor": "c1"}}),
        _resp({}, status=429, headers={"Retry-After": "1"}),
        _resp({"ok": True, "messages": [{"ts": "1"}], "has_more": False}),
    ]
    with mock.patch.object(slack_fetcher.requests, "get", side_effect=pages) as get, \
            mock.patch.object(slack_fetcher.time, "sleep") as sleep:
        out = slack_fetcher.fetch_slack_history_since("C1", "xoxp-t", oldest_ts=1700000000)
    assert [m["ts"] for m in out] == ["3", "2", "1"]
    sleep.assert_called_once_with(1)
    assert get.call_args_list[0].kwargs["params"]["oldest"].startswith("1700000000")
    assert get.call_args_list[2].kwargs["params"]["cursor"] == "c1"


def test_fetch_since_returns_partial_on_slack_error():
    pages = [
        _resp({"ok": True, "messages": [{"ts": "3"}], "has_more": True,
               "response_metadata": {"next_cursor": "c1"}}),
        _resp({"ok": False, "error": "ratelimited"}),
    ]
    with mock.patch.object(slack_fetcher.requests, "get", side_effect=pages):
        out = slack_fetcher.fetch_slack_history_since("C1", "xoxp-t", oldest_ts=0)
    assert [m["ts"] for m in out] == ["3"]


# ------------------------------------------------------------------ real multi-line posts

MULTILINE = msg(20, (
    "【事務局からのサポーター募集】\n\n【SJ中高部】5-7\n"
    "５．業務名称:    SJ中高部 スポーツ大会：男子バスケットボール予選 主審（6月20日）\n"
    "審判 26年6月20日（土）8：50 〜 12：05\n"
    "カテゴリ: スポーツ大会\n場所:    中高SJ\n"
    "業務の詳細:    \n集合場所：ヤード本部前\n試合の進行・判定\n"
    "６．業務名称:    SJ中高部 スポーツ大会：女子バレー 線審\n"
    "カテゴリ: スポーツ大会\n場所:    中高SJ\n貢献点：2点\n"
))


def test_multiline_post_fields_stop_at_line_break():
    a, b = parse_message(MULTILINE)
    assert a.title == "SJ中高部 スポーツ大会：男子バスケットボール予選 主審（6月20日）"
    assert a.category_raw == "スポーツ大会"          # not "スポーツ大会\n場所: 中高SJ"
    assert b.title == "SJ中高部 スポーツ大会：女子バレー 線審" and b.points == "2点"


def test_tag_only_heading_is_skipped_for_unlabelled_posts():
    m = msg(21, "━━━━━━━━━━\n 【再告知】 \n 保護者会ボランティア募集！\n━━━━━━━━━━\n募集人数：12名\n貢献点：2点")
    (e,) = parse_message(m)
    assert e.title == "保護者会ボランティア募集！"


# ------------------------------------------------------------------ multiple channels

import argparse
import json

from src.categories import cli


def _args(**kw):
    base = dict(channel=None, from_file=None, since="2025-01-01", days=None, force_reauth=False, index=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_same_ts_in_two_channels_are_two_postings():
    m = msg(1, HEADER + job("SJ幼小部 ランチ当番", "ランチ当番") + FOOTER)   # identical ts + text
    entries = parse_messages([m], channel="C_NEW") + parse_messages([m], channel="C_OLD")
    assert {e.channel for e in entries} == {"C_NEW", "C_OLD"}
    idx = build_index(entries)
    assert idx.categories[0].posting_count == 2


def test_resolve_channels_prefers_flags_then_settings(monkeypatch):
    monkeypatch.setattr(cli.settings, "CATEGORY_CHANNEL_IDS", ["C_ENV1", "C_ENV2"])
    assert cli.resolve_channels(_args()) == ["C_ENV1", "C_ENV2"]
    assert cli.resolve_channels(_args(channel=["C_FLAG"])) == ["C_FLAG"]


def test_refresh_merges_spellings_across_files(tmp_path, capsys):
    new = [msg(1, HEADER + job("SJ幼小部 ランチ当番", "ランチ当番") + FOOTER)]
    old = [msg(1, HEADER + job("SJ幼小部 ランチ当番", "ランチ 当番") + FOOTER),
           msg(2, HEADER + job("SJ幼小部 教科書配布", "教科書配布") + FOOTER)]
    (tmp_path / "school2026.json").write_text(json.dumps(new), encoding="utf-8")
    (tmp_path / "school2025.json").write_text(json.dumps(old), encoding="utf-8")
    out = tmp_path / "idx.json"
    cli.cmd_refresh(_args(from_file=[str(tmp_path / "school2026.json"), str(tmp_path / "school2025.json")],
                          index=str(out)))
    idx = CategoryIndex.load(out)
    lunch = next(c for c in idx.categories if c.name == "ランチ当番")
    assert lunch.posting_count == 2 and set(lunch.variants) == {"ランチ当番", "ランチ 当番"}
    assert {p["channel"] for p in idx.postings} == {"school2026", "school2025"}


def test_live_refresh_scans_every_channel_and_survives_one_failing(tmp_path):
    calls = []

    def fake_fetch(channel, token, oldest):
        calls.append(channel)
        return [] if channel == "C_BAD" else [msg(1, HEADER + job("SJ幼小部 ランチ当番", "ランチ当番") + FOOTER)]

    out = tmp_path / "idx.json"
    with mock.patch("src.auth.get_slack_token", return_value="xoxp-t"), \
            mock.patch("src.slack_fetcher.fetch_slack_history_since", side_effect=fake_fetch):
        cli.cmd_refresh(_args(channel=["C_OK", "C_BAD", "C_OLD"], index=str(out)))
    assert calls == ["C_OK", "C_BAD", "C_OLD"]
    idx = CategoryIndex.load(out)
    assert idx.categories[0].posting_count == 2          # C_OK + C_OLD; C_BAD contributed nothing


# ------------------------------------------------------------------ fetch window

def test_window_defaults_to_fixed_start_date():
    oldest, since = cli.resolve_window(_args())
    assert since == "2025-01-01" and oldest == 1735689600.0     # 2025-01-01T00:00:00Z


def test_days_flag_overrides_start_date():
    oldest, since = cli.resolve_window(_args(days=30))
    assert abs(oldest - (__import__("time").time() - 30 * 86400)) < 5


def test_invalid_start_date_exits_cleanly(capsys):
    import pytest
    with pytest.raises(SystemExit):
        cli.resolve_window(_args(since="2025/01/01"))
    assert "YYYY-MM-DD" in capsys.readouterr().out


def test_live_refresh_passes_start_date_to_slack_and_records_it(tmp_path):
    seen = []

    def fake_fetch(channel, token, oldest):
        seen.append(oldest)
        return [msg(1, HEADER + job("SJ幼小部 ランチ当番", "ランチ当番") + FOOTER)]

    out = tmp_path / "idx.json"
    with mock.patch("src.auth.get_slack_token", return_value="xoxp-t"), \
            mock.patch("src.slack_fetcher.fetch_slack_history_since", side_effect=fake_fetch):
        cli.cmd_refresh(_args(channel=["C_A"], index=str(out)))
    assert seen == [1735689600.0]
    assert CategoryIndex.load(out).since == "2025-01-01"


# ------------------------------------------------------------------ regressions from the real channel

from src.categories.parser import clean_slack_text


def _one(text):
    (e,) = parse_message(msg(50, text))
    return e


def test_category_stops_before_trailing_place_label():
    # seen in production: "スポーツ大会 場所:    中高SJ" became a separate category
    flat = job("SJ中高部 スポーツ大会 主審", "スポーツ大会 場所:    中高SJ")
    assert _one(flat).category_raw == "スポーツ大会"
    # an unlisted label on the same line must also end the category
    assert _one(job("SJ中高部 受付", "受付 備考: 要連絡")).category_raw == "受付"


def test_place_suffix_no_longer_creates_duplicate_categories():
    msgs = [
        msg(1, job("SJ中高部 スポーツ大会", "スポーツ大会 場所: 中高SJ")),
        msg(2, job("SJ中高部 スポーツ大会", "スポーツ大会 場所:      中高SJ")),
        msg(3, job("SJ中高部 交通安全当番", "交通安全当番 場所:      中高SJ")),
        msg(4, job("SJ中高部 交通安全当番", "交通安全当番")),
    ]
    idx = build_index(parse_messages(msgs))
    assert sorted(idx.options) == ["スポーツ大会", "交通安全当番"]
    assert [c.posting_count for c in idx.categories] == [2, 2]
    assert idx.review_pairs == []


def test_slack_markup_is_decoded():
    t = clean_slack_text("<!channel> A&amp;B &lt;ok&gt; <https://app.sfjs.org/|ポータル> <https://x.example> <@U123ABC> <!here>")
    assert t == "@channel A&B <ok> ポータル (https://app.sfjs.org/) https://x.example @user @here"


def test_body_keeps_readable_mentions_for_templates():
    e = _one("<!channel> *在宅ボランティア募集！* 募集人数：1人 貢献点：1点 <https://app.sfjs.org/|応募>")
    assert "<!channel>" not in e.body and "@channel" in e.body
    assert "応募 (https://app.sfjs.org/)" in e.body


def test_headings_from_real_unlabelled_posts():
    tail = " 募集人数：2名 貢献点：2点"
    cases = {
        "<!channel> 理事会 サポーター募集 *【スタジオかけはし カメラマン募集 】* 補習校でイヤーブック作成のために" + tail:
            "スタジオかけはし カメラマン募集",
        "<!channel> *【再告知】* * 保護者会ボランティア募集！* *【 中高部駄菓子フェス当日ボランティア募集】* 11月7日(土)" + tail:
            "保護者会ボランティア募集！",
        "*秋まつり はっぴ洗濯 在宅ボランティア募集！* 10月10日（土）にSJ幼小部で実施される「秋まつり」" + tail:
            "秋まつり はっぴ洗濯 在宅ボランティア募集！",
        "<!channel> 新年お楽しみ会在宅ボランティア募集! 小さいお子様のいるご家庭向け!在宅ボランティア募集!" + tail:
            "新年お楽しみ会在宅ボランティア募集!",
        "26年度後期：ITアドミン&amp;サポートデスク募集（SF/SJ: ITサポーター）" + tail:
            "26年度後期：ITアドミン&サポートデスク募集（SF/SJ: ITサポーター）",
    }
    for text, title in cases.items():
        assert _one(text).title == title


def test_title_whitespace_and_bold_markers_collapsed():
    assert _one(job("SJ幼小部  ランチ当番 26年04月04日", "ランチ当番")).title == "SJ幼小部 ランチ当番"
