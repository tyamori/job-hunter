import os
import asyncio
import json
import traceback
import logging
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

# 個別の求人処理を行う非同期関数
async def process_single_job(page, job_info, index, total):
    job_link = job_info.get('link', 'リンク不明')
    job_title = job_info.get('title', 'タイトル不明')
    logging.info(f"[{index+1}/{total}] 処理開始: {job_title} ({job_link})")

    # 1. テキスト取得
    await asyncio.sleep(1)
    page_content = await get_job_page_content(page, job_link, job_title)

    analysis_result = None
    if page_content:
        # 2. LLM解析
        analysis_result = await analyze_job_page_with_gpt(page_content, job_title, job_link)
    else:
        # テキスト取得失敗
        logging.warning(f"  [{job_title}] テキスト取得失敗のためLLM解析をスキップ")
        analysis_result = {"元タイトル": job_title, "元リンク": job_link, "エラー": "ページテキスト取得失敗"}

    return analysis_result

# メインの処理関数
async def scrape_and_analyze(force_reload: bool, headless: bool):
    # 環境変数のチェック
    if not EMAIL or not PASSWORD:
        logging.error("エラー: 環境変数 FINDY_EMAIL または FINDY_PASSWORD が設定されていません。")
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
                             logging.info(f"キャッシュにエラー記録あり、再試行: {link}")
                        links_to_process.append(job_info)
                    # else:
                    #     logging.debug(f"キャッシュヒット: {link}") # デバッグ用
                else:
                    logging.warning(f"無効なリンクまたはタイトル不明のためスキップ: {job_info}")

            logging.info(f"--- 今回解析が必要な求人数: {len(links_to_process)} 件 --- ")

            # === 各求人詳細ページのテキスト取得 & LLM解析 ===
            if links_to_process:
                logging.info("\n--- 詳細ページのテキスト取得とLLM解析開始 (1秒間隔) ---")
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

                logging.info(f"--- 詳細ページのテキスト取得とLLM解析完了 ({len(newly_analyzed_jobs)} 件成功) --- ")
            else:
                logging.info("テキストを取得・解析する新しい求人はありません。")

        except Exception as e:
            logging.error(f"メイン処理で予期せぬエラーが発生しました: {e}")
            traceback.print_exc()
            logging.warning("エラーが発生しましたが、途中までの結果をキャッシュに保存します。")
        finally:
            # === 結果の保存 ===
            save_cache(cached_results)

            # === コンソール出力 (最終結果) ===
            # logging.info("\n--- 最終結果（キャッシュ全体から最初の5件）--- ") # 冗長なのでコメントアウト
            # final_results_list = list(cached_results.values())
            # for i, job_data in enumerate(final_results_list[:5]):
            #     logging.info(f"\n--- 求人 {i+1} ---") # print -> logging
            #     for key, value in job_data.items():
            #         logging.info(f"{key}: {value}") # print -> logging 