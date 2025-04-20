import os
import asyncio
import argparse
from dotenv import load_dotenv

# 相対インポートに変更
from findy_scraper.application import main_logic

async def main():
    # 環境変数を読み込む
    load_dotenv()

    # コマンドライン引数の設定
    parser = argparse.ArgumentParser(description='Findyからいいねされた求人情報を取得し、LLMで解析します。')
    parser.add_argument(
        '--force-reload',
        action='store_true',
        help='キャッシュを無視して全ての求人を再取得・再解析します。'
    )
    parser.add_argument(
        '--no-headless',
        action='store_false',
        dest='headless', # headlessをTrueにするのをデフォルトに
        help='ブラウザを非ヘッドレスモードで起動します（デバッグ用）。'
    )
    parser.set_defaults(headless=True)
    args = parser.parse_args()

    await main_logic.scrape_and_analyze(args.force_reload, args.headless)

if __name__ == "__main__":
    # 実行環境のイベントループを取得または新規作成
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 'RuntimeError: There is no current event loop...'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(main()) 