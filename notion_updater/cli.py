import os
import asyncio
import logging
from dotenv import load_dotenv
from notion_client import AsyncClient

# 相対インポートに変更
from notion_updater.application import main_logic

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    # 環境変数を読み込む
    load_dotenv()
    NOTION_API_KEY = os.getenv('NOTION_API_KEY')
    NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logging.error("環境変数 NOTION_API_KEY または NOTION_DATABASE_ID が設定されていません。")
        return

    # Notionクライアント初期化
    async with AsyncClient(auth=NOTION_API_KEY, timeout_ms=60000, log_level=logging.WARNING) as client: # タイムアウト延長、ログレベル調整
        await main_logic.run(client, NOTION_DATABASE_ID)

if __name__ == "__main__":
    asyncio.run(main()) 