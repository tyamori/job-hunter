import logging
import os
from notion_client import AsyncClient

# 相対インポートに変更
from notion_updater.infrastructure import file_handler, notion_api
from notion_updater.core import notion_formatter, models

async def run(client: AsyncClient, database_id: str):
    """Notion Updater のメイン処理を実行する"""
    # 1. データベーススキーマの確認と自動更新
    db_properties = await notion_api.ensure_database_schema(client, database_id)
    if db_properties is None:
         logging.error("データベーススキーマの準備に失敗しました。処理を中断します。")
         return
    logging.info("データベーススキーマの準備が完了しました。")

    # 2. JSONファイル読み込み
    all_job_data = file_handler.load_job_data()
    if all_job_data is None:
        logging.error("求人データの読み込みに失敗しました。処理を中断します。")
        return

    # 3. Notionから既存URLとページID取得
    url_property_name = "URL"
    existing_pages_map = await notion_api.get_existing_notion_pages(client, database_id, url_property_name)

    if existing_pages_map is None:
        logging.error("既存ページ情報の取得に失敗したため、処理を中断します。")
        return

    # 4. 差分をNotionに追加または更新
    new_jobs_count = 0
    updated_jobs_count = 0
    failed_jobs_count = 0
    skipped_due_to_error_count = 0
    skipped_due_to_invalid_url = 0

    logging.info("--- Notionへのデータ反映処理開始 ---")
    for job_data in all_job_data:
        # LLM解析時のエラーチェック
        if job_data.get("エラー"):
             logging.info(f"  情報: LLM解析エラーが含まれるためスキップ: {job_data.get('元リンク', 'リンク不明')} ({job_data.get('エラー')})")
             skipped_due_to_error_count += 1
             continue

        # URLの取得と検証 (URLキーを優先、なければ元リンク)
        job_url = job_data.get('URL') or job_data.get('元リンク')
        if not job_url or not isinstance(job_url, str) or not job_url.startswith('http'):
             logging.warning(f"  警告: 無効なURLまたはURLが見つからないためスキップ: {job_data.get('会社名', '会社名不明')} (URL: {job_url})")
             skipped_due_to_invalid_url += 1
             continue

        # 既存ページに含まれているかチェック
        if job_url in existing_pages_map:
             # --- 更新処理 ---
             page_id = existing_pages_map[job_url]
             notion_properties = notion_formatter.convert_to_notion_properties(job_data, db_properties)

             # 更新に必要なプロパティがあるかチェック (Titleは更新対象外でもOK)
             if not notion_properties:
                  logging.warning(f"  URL: {job_url} (Page ID: {page_id}) - 更新するプロパティがありません。スキップします。")
                  continue

             success = await notion_api.update_notion_page(client, page_id, notion_properties, models.MANUAL_UPDATE_EXCLUDE_PROPS)
             if success:
                  updated_jobs_count += 1
             else:
                  failed_jobs_count += 1
        else:
             # --- 新規作成処理 ---
             notion_properties = notion_formatter.convert_to_notion_properties(job_data, db_properties)

             # 必須プロパティ(Title, URL)の最終チェック
             title_prop_name = next((k for k, v in db_properties.items() if v['type'] == 'title'), None)
             if not title_prop_name or title_prop_name not in notion_properties:
                  logging.error(f"  致命的エラー: 必須プロパティ '{title_prop_name}' が最終データに含まれていません。スキップ: {job_url}")
                  failed_jobs_count += 1
                  continue
             if url_property_name not in notion_properties:
                  logging.error(f"  致命的エラー: 必須プロパティ '{url_property_name}' が最終データに含まれていません。スキップ: {job_url}")
                  failed_jobs_count += 1
                  continue

             success = await notion_api.create_notion_page(client, database_id, notion_properties)
             if success:
                 new_jobs_count += 1
             else:
                 failed_jobs_count += 1
        # else:
        #      logging.debug(f"  情報: 既存のためスキップ: {job_url}") # この分岐は到達しないはず

    logging.info("--- Notionへのデータ反映処理完了 ---")
    logging.info(f"新規追加成功: {new_jobs_count} 件")
    logging.info(f"更新成功: {updated_jobs_count} 件")
    if failed_jobs_count > 0:
         logging.warning(f"追加/更新失敗: {failed_jobs_count} 件")
    if skipped_due_to_error_count > 0:
         logging.info(f"LLM解析エラーのためスキップ: {skipped_due_to_error_count} 件")
    if skipped_due_to_invalid_url > 0:
         logging.info(f"無効なURLのためスキップ: {skipped_due_to_invalid_url} 件") 