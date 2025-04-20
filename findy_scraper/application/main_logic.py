import os
import asyncio
import json
import traceback
from dotenv import load_dotenv

# 相対インポートに変更
from findy_scraper.infrastructure.playwright_handler import PlaywrightManager, login_findy, get_all_liked_job_links, get_job_page_content
from findy_scraper.infrastructure.llm_analyzer import analyze_job_page_with_gpt
from findy_scraper.infrastructure.cache_manager import load_cache, save_cache

# 環境変数を読み込む (cli.pyでも読むが、念のためここでも)
load_dotenv()

# ログイン情報を環境変数から取得
EMAIL = os.getenv('FINDY_EMAIL')
PASSWORD = os.getenv('FINDY_PASSWORD')

# メインの処理関数
async def scrape_and_analyze(force_reload: bool, headless: bool):
    # 環境変数のチェック
    if not EMAIL or not PASSWORD:
        print("エラー: 環境変数 FINDY_EMAIL または FINDY_PASSWORD が設定されていません。")
        return

    # キャッシュのロード
    cached_results = load_cache(force_reload)

    all_job_links_info = [] # 全ページのリンク情報 [{title: str, link: str}]
    links_to_process = []   # 今回処理が必要なリンク情報
    newly_analyzed_jobs = [] # 新しく解析されたジョブ

    # Playwrightの管理
    async with PlaywrightManager(headless=headless) as page:
        try:
            # === ログイン ===
            await login_findy(page, EMAIL, PASSWORD)

            # === いいねページの全リンク収集 ===
            all_job_links_info = await get_all_liked_job_links(page)

            # === 解析対象の選定 ===
            for job_info in all_job_links_info:
                link = job_info.get('link')
                if link and link != "不明":
                    # キャッシュにない or キャッシュがエラーだった場合に対象とする
                    cache_key = link
                    cached_entry = cached_results.get(cache_key)

                    if not cached_entry or cached_entry.get("エラー"):
                        if cached_entry and cached_entry.get("エラー"):
                             print(f"キャッシュにエラー記録あり、再試行: {link}")
                        links_to_process.append(job_info)
                    # else:
                    #     print(f"キャッシュヒット: {link}") # デバッグ用
                else:
                    print(f"無効なリンクまたはタイトル不明のためスキップ: {job_info}")

            print(f"--- 今回解析が必要な求人数: {len(links_to_process)} 件 --- ")

            # === 各求人詳細ページのテキスト取得 & LLM解析 ===
            if links_to_process:
                print("\n--- 詳細ページのテキスト取得とLLM解析開始 (1秒間隔) ---")
                tasks = []
                for i, job_info in enumerate(links_to_process):
                    tasks.append(process_single_job(page, job_info, i, len(links_to_process)))

                # asyncio.gatherでタスクを実行
                results = await asyncio.gather(*tasks)

                # 結果をキャッシュに反映
                for result in results:
                    if result:
                        link = result.get("元リンク")
                        if link:
                             cached_results[link] = result
                             if not result.get("エラー"):
                                newly_analyzed_jobs.append(result)

                print(f"--- 詳細ページのテキスト取得とLLM解析完了 ({len(newly_analyzed_jobs)} 件成功) --- ")
            else:
                print("テキストを取得・解析する新しい求人はありません。")

        except Exception as e:
            print(f"メイン処理で予期せぬエラーが発生しました: {e}")
            traceback.print_exc()
            print("エラーが発生しましたが、途中までの結果をキャッシュに保存します。")
        finally:
            # === 結果の保存 ===
            save_cache(cached_results)

            # === コンソール出力 (最終結果) ===
            print("\n--- 最終結果（キャッシュ全体から最初の5件）--- ")
            final_results_list = list(cached_results.values())
            for i, job_data in enumerate(final_results_list[:5]):
                print(f"\n--- 求人 {i+1} ---")
                for key, value in job_data.items():
                    print(f"{key}: {value}") 