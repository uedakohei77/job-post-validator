# -*- coding: utf-8 -*-
import argparse
import os
import sys
from config import settings
from src.auth import get_slack_token
from src.slack_fetcher import fetch_slack_history, extract_message_texts
from src.validator import validate_volunteer_post

# Mock / Dry-run postings to demonstrate the tool instantly without Slack API
DRY_RUN_POSTS = [
    {
        "description": " 業務名称: SJ幼小部 教科書配布",
        "text": "@channel 【事務局からのサポーター募集】 【SJ校 幼小部】 業務名称: SJ幼小部 教科書配布 26年04月04日 カテゴリ:教科書配布 業務開始日時：2026年04月04日（土）午前09時00分 業務終了日時：2026年04月04日（土）午後10時00分 申込開始日時：2026年03月13日（金）午前9時 申込終了日時：2026年03月19日（木）午後11時59分 対象：小学部保護者 募集人数: 12人 貢献点：各1.0点 選出方法：抽選 業務詳細：職員室前に置いてある学級毎に仕分け済みの教科書が入っている段ボール箱を各教室に運ぶ。(各学年2名で作業） 担任の要望如何で、必要であれば教室内で児童に配布する手伝いをする。空になった段ボール箱を折りたたんでリサイクル箱に破棄する。 ※体力に自信のある方募集。台車を持参できる方はお持ちいただけると有難いです。 集合場所：職員室前 ーーーーーーーーーーーーーーーーーーーーー 業務名称：SJ幼小部 ランチ当番 26年04月04日,11日,18日,25日 (土) 業務開始日時：2026年04月04日,11日,18日,25日（土）午前11時40分 業務終了日時：2026年04月04日,11日,18日,25日（土）午後12時30分 申込開始日時：2026年 3月18日（水）午前9時 申込終了日時：2026年 3月28日（土）午後11時59分 対象：小学部保護者 募集人数: ８人 貢献点：各1.0点 選出方法：抽選 業務詳細：職員室前に置いてある番号札を取ってから、指定箇所でお昼休み中の児童の見守り、清掃（ごみ拾い）など。＊この当番の業務は小学部のお昼休みの見守りです。幼稚部の保護者も申し込めますが、幼稚部の幼児の様子は見られませんhttps://docs.google.com/document/d/11KkNaWGTTjtm0FJG0TB6MN8cfPPpMarsAOY18Yry-Jc/edit?usp=sharing　 ーーーーーーーーーーーーーーーーーーーーーー ＊補習校ポータルリンク(応募はこちらから) https://app.sfjs.org/ ＊補習校サポーター使用方法についてはこちらを参照。 https://docs.google.com/presentation/d/1OlxYNTGWw4NlhYIRckpkffHJa9qBI6OOfTQz8fyBLiw/edit?usp=sharing ＊お問い合わせはこちらから Google Form http://go.sfjs.org/newticket ※お問い合わせ前にソリューションのナレッジベースFAQをご確認ください。 https://sfjs1969.notion.site"
    },
    {
        "description": "業務名称:SJ 中高部 交通安全当番",
        "text": "@channel 【事務局からのサポーター募集】 【SJ中高部】 業務名称:SJ 中高部 交通安全当番（下校時） 26年04月04日 カテゴリ: 交通安全当番 対象学校・学年: SJ小6、SJ中1, SJ中2, SJ中3, SJ高1, 業務開始日時:　2026年04月04日（土）午後３時05分 業務終了日時: 2026年04月04日（土）午後3時35分 申込開始日時：2026年03月11日（水）午前9時 申込終了日時：2026年03月18日（水）午後11時59分 対象：小学部6年生から高等部1年生保護者 募集人数: 3人 貢献点：各0.5点 選出方法：抽選 業務詳細： 中高部正門前に集合。1名は校門前で駐車場を横切る生徒・保護者の誘導、1名は駐車場入り口で車を誘導、 1名は生徒待ちの車の先頭車を誘導。各自は、前の車が動いたら前に詰めるように指示をする。集合場所:中高SJ駐車場（Hyannisport Rd.） https://docs.google.com/document/d/11KkNaWGTTjtm0FJG0TB6MN8cfPPpMarsAOY18Yry-Jc/edit?usp=sharing ＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿ 業務名称:SJ 中高部 交通安全当番（下校時） 26年04月11日 カテゴリ: 交通安全当番 対象学校・学年: SJ小6、SJ中1, SJ中2, SJ中3, SJ高1, 業務開始日時:　2026年04月11日（土）午後３時05分 業務終了日時: 2026年04月11日（土）午後3時35分 申込開始日時：2026年03月11日（水）午前9時 申込終了日時：2026年03月18日（水）午後11時59分 対象：小学部6年生から高等部1年生保護者 募集人数: 3人 貢献点：各0.5点 選出方法：抽選 業務詳細： 中高部正門前に集合。1名は校門前で駐車場を横切る生徒・保護者の誘導、1名は駐車場入り口で車を誘導、 1名は生徒待ちの車の先頭車を誘導。各自は、前の車が動いたら前に詰めるように指示をする。集合場所:中高SJ駐車場（Hyannisport Rd.） https://docs.google.com/document/d/11KkNaWGTTjtm0FJG0TB6MN8cfPPpMarsAOY18Yry-Jc/edit?usp=sharing ＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿ 業務名称:SJ 中高部 交通安全当番（下校時） 26年04月18日 カテゴリ: 交通安全当番 対象学校・学年: SJ小6、SJ中1, SJ中2, SJ中3, SJ高1, 業務開始日時:　2026年04月18日（土）午後３時05分 業務終了日時: 2026年04月18日（土）午後3時35分 申込開始日時：2026年03月11日（水）午前9時 申込終了日時：2026年03月18日（水）午後11時59分 対象：小学部6年生から高等部1年生保護者 募集人数: 3人 貢献点：各0.5点 選出方法：抽選 業務詳細： 中高部正門前に集合。1名は校門前で駐車場を横切る生徒・保護者の誘導、1名は駐車場入り口で車を誘導、 1名は生徒待ちの車の先頭車を誘導。各自は、前の車が動いたら前に詰めるように指示をする。集合場所:中高SJ駐車場（Hyannisport Rd.） https://docs.google.com/document/d/11KkNaWGTTjtm0FJG0TB6MN8cfPPpMarsAOY18Yry-Jc/edit?usp=sharing ＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿ 業務名称:SJ 中高部 交通安全当番（下校時） 26年04月25日 カテゴリ: 交通安全当番 対象学校・学年: SJ小6、SJ中1, SJ中2, SJ中3, SJ高1, 業務開始日時:　2026年04月25日（土）午後３時05分 業務終了日時: 2026年04月25日（土）午後3時35分 申込開始日時：2026年03月11日（水）午前9時 申込終了日時：2026年03月18日（水）午後11時59分 対象：小学部6年生から高等部1年生保護者 募集人数: 3人 貢献点：各0.5点 選出方法：抽選 業務詳細： 中高部正門前に集合。1名は校門前で駐車場を横切る生徒・保護者の誘導、1名は駐車場入り口で車を誘導、 1名は生徒待ちの車の先頭車を誘導。各自は、前の車が動いたら前に詰めるように指示をする。集合場所:中高SJ駐車場（Hyannisport Rd.） https://docs.google.com/document/d/11KkNaWGTTjtm0FJG0TB6MN8cfPPpMarsAOY18Yry-Jc/edit?usp=sharing ーーーーーーーーーーーーーーーーーーーーーー ＊補習校ポータルリンク(応募はこちらから) https://app.sfjs.org/ ＊補習校サポーター使用方法についてはこちらを参照。 https://docs.google.com/presentation/d/1OlxYNTGWw4NlhYIRckpkffHJa9qBI6OOfTQz8fyBLiw/edit?usp=sharing ＊お問い合わせはこちらから Google Form http://go.sfjs.org/newticket ※お問い合わせ前にソリューションのナレッジベースFAQをご確認ください。 https://sfjs1969.notion.site"
    },
    {
        "description": "修了記念品であるスポーツサックの仕分け",
        "text": "@channel ━━━━━━━━━━━━━━━━  :four_leaf_clover: 中高部の卒業、修了記念品であるスポーツサックの仕分けと搬入ボランティア募集（リマインダー） ━━━━━━━━━━━━━━━━ 業務開始日時：2026年3月11日（水） 業務終了日時：2026年3月14日（土） 申込開始日時：2026年3月6日（金）10時 申込終了日時：2026年3月9日（月）21時 対象：中高部保護者 募集人数：1人 貢献点：1点 選出方法：抽選 業務詳細： 卒業・修了記念品であるスポーツサックを保護者会役員から受け取り自宅で仕分けして保管、3月14日(土)の朝に補修校の職員室まで搬入していただける方を募集します。 ①3月11日(水)以降、保護者会役員が記念品をご自宅にお届けます。ご自宅でクラスごと（中1ー高2）に仕分けして保管し、3月14日(土)８時20分までにJFK校の職員室に搬入可能な方 ②詳細を保護者会役員とSlackでやり取りができること ③記念品であるスポーツサック（200枚ほど）の入ったダンボールを保管できるスペースがあること ＊選出された方には3月10日頃にSlackにてご連絡しますので、必ずSlackのご確認をお願いいたします。 _______________________________________ ＊応募はこちらから（補習校ポータル） https://app.sfjs.org/ ＊補習校サポーターシステム使用方法 https://docs.google.com/presentation/d/1pnryDYqYdgbjqpIgPExbkf0pD9y7-8N4/ ＊お問い合わせはこちらから Freshdesk http://go.sfjs.org/newticket ＊お問い合わせ前にソリューションのナレッジベースFAQをご確認ください。 https://sfjs1969.notion.site ＊お問い合わせへの対応は保護者会側で緊急と判断したもの以外は平日のみとさせていただきます"
    },
]


def print_report(post_text, report):
    """Prints the structured Pydantic report in a beautiful, formatted terminal box."""
    border = "=" * 80
    sub_border = "-" * 80
    print(border)
    print("VOLUNTEER POST VALIDATION REPORT")
    print(border)
    print(f"POST TEXT:\n{post_text.strip()}")
    print(sub_border)
    
    status_str = "VALID" if report.is_valid else "INVALID"
    status_color = "\033[92m" if report.is_valid else "\033[91m"
    reset_color = "\033[0m"
    
    print(f"Status:            {status_color}{status_str}{reset_color}")
    print(f"Category:          {report.category}")
    print(f"Duration (Hours):  {report.extracted_duration_hours} hrs")
    print(f"Offered Points:    {report.extracted_points} pts")
    print(f"Points Per Hour:   {report.assigned_points_per_hour:.3f} pts/hr")
    print(f"\nReasoning:\n{report.reasoning}")
    
    if report.corrections_needed:
        print(f"\nCorrections Needed:")
        for idx, correction in enumerate(report.corrections_needed, 1):
            print(f"  {idx}. {correction}")
            
    print(border + "\n")


def run_dry_run():
    """Runs validation on pre-configured test posts to verify validator logic."""
    print("\nRunning Validator in Dry-Run Mode with Sample Postings...\n")
    for post in DRY_RUN_POSTS:
        print(f"Testing Case: {post['description']}")
        try:
            report = validate_volunteer_post(post["text"])
            print_report(post["text"], report)
        except Exception as e:
            print(f"Failed to validate post: {e}\n")


def run_interactive():
    """Prompts the user to type or paste a post to validate interactively."""
    print("\n" + "="*80)
    print("INTERACTIVE VALIDATOR MODE")
    print("="*80)
    print("Enter the volunteer job posting text below. Press Ctrl+D (or Ctrl+Z on Windows) followed by Enter when done:")
    print("-"*80)
    
    try:
        post_text = sys.stdin.read().strip()
        if not post_text:
            print("No input provided.")
            return
            
        print("\nValidating posting...")
        report = validate_volunteer_post(post_text)
        print_report(post_text, report)
    except KeyboardInterrupt:
        print("\nInteractive mode cancelled.")


def main():
    parser = argparse.ArgumentParser(
        description="Volunteer Job Post Validator - Validates hours and reward points using Gemini."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validation on pre-configured test cases (useful for testing LLM logic)."
    )
    group.add_argument(
        "--interactive",
        action="store_true",
        help="Paste a volunteer post text manually to run validation."
    )
    parser.add_argument(
        "--force-reauth",
        action="store_true",
        help="Force the Slack OAuth authorization flow to run again to overwrite token."
    )
    
    args = parser.parse_args()
    
    # 1. Check for Dry Run
    if args.dry_run:
        run_dry_run()
        return
        
    # 2. Check for Interactive
    if args.interactive:
        run_interactive()
        return
        
    # 3. Standard Slack-fetching execution
    print("Starting Volunteer Job Post Validator...")
    
    # Check if Gemini key is set before starting Slack auth
    if not settings.GEMINI_API_KEY:
        print("\n[!] Error: GEMINI_API_KEY environment variable is missing.")
        print("Please configure it in a .env file or export it in your shell.")
        print("Example: export GEMINI_API_KEY='your_api_key'\n")
        print("Tip: You can still run the CLI without Slack configured using local mock data:")
        print("  python3 src/main.py --dry-run")
        print("Or validate manual postings:")
        print("  python3 src/main.py --interactive\n")
        sys.exit(1)
        
    # Check Slack Configuration
    channel_id = settings.SLACK_CHANNEL_ID
    if not channel_id:
        print("\n[!] Error: SLACK_CHANNEL_ID environment variable is missing in your .env file.")
        print("Tip: If you do not have Slack set up yet, you can test the validation logic with:")
        print("  python3 src/main.py --dry-run")
        print("Or check the interactive mode:")
        print("  python3 src/main.py --interactive\n")
        sys.exit(1)
        
    # Run Slack Auth flow to retrieve/validate User token
    token = get_slack_token(force_reauth=args.force_reauth)
    
    # Fetch latest postings from Slack
    print(f"Fetching latest postings from Slack Channel: {channel_id}...")
    messages = fetch_slack_history(channel_id, token, limit=5)
    
    post_texts = extract_message_texts(messages)
    if not post_texts:
        print("No active postings found in Slack channel history.")
        return
        
    print(f"Found {len(post_texts)} postings. Validating postings...\n")
    
    for idx, post_text in enumerate(post_texts, 1):
        print(f"[{idx}/{len(post_texts)}] Processing posting...")
        try:
            report = validate_volunteer_post(post_text)
            print_report(post_text, report)
        except Exception as e:
            print(f"Failed to validate posting: {e}\n")


if __name__ == "__main__":
    # Set Python module search path to project root to allow config & src imports
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    main()
