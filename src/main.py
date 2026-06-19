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
        "description": "標準的なボランティア（有効な投稿）",
        "text": "コミュニティセンターでのイベント受付ボランティアを募集します。日時：今週金曜日 13:00〜17:00 (4時間)。謝礼ポイントは4ポイントです。"
    },
    {
        "description": "肉体労働ボランティア（有効な投稿 - 報酬高め）",
        "text": "【急募】公園の整備作業のため、シャベルでの穴掘りや木屑の運搬作業（体力仕事）をお願いできる方を募集します。土曜日 9:00〜12:00 (3時間)。力仕事のため、10ポイントを付与します。"
    },
    {
        "description": "受動的な保管ボランティア（有効な投稿 - 保管例外適用）",
        "text": "災害用備蓄品（ダンボール15箱分）を1ヶ月間、湿気のないガレージまたは倉庫スペースに保管させていただける方を募集しています。謝礼ポイントは一律3ポイントです。"
    },
    {
        "description": "標準的な作業でポイントが過剰なケース（無効な投稿）",
        "text": "簡単な書類の整理・ファイリングのお手伝いをお願いします。来週火曜日 14:00〜16:00 (2時間)。謝礼ポイントとして35ポイントをプレゼントします。"
    },
    {
        "description": "受動的保管でポイントが過剰なケース（無効な投稿）",
        "text": "イベント用テント（畳んだ状態）をご自宅の庭または物置で2週間保管させてください。謝礼ポイントとして60ポイントを差し上げます。"
    }
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
