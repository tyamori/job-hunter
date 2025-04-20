import json
import logging
import os # osモジュールをインポート

# キャッシュディレクトリとファイル名を定義
CACHE_DIR = ".cache"
CACHE_FILE_NAME = "analyzed_findy_jobs.json"
CACHE_FILE = os.path.join(CACHE_DIR, CACHE_FILE_NAME) # 正しいパスを生成

def load_job_data() -> list[dict] | None:
    """JSONファイルから求人データを読み込む"""
    try:
        # 修正: 正しいCACHE_FILEパスを使用
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            all_job_data = json.load(f)
        logging.info(f"{CACHE_FILE} から {len(all_job_data)} 件の求人データを読み込みました。")
        return all_job_data
    except FileNotFoundError:
        # 修正: エラーメッセージも正しいファイルパスを表示するように
        logging.error(f"{CACHE_FILE} が見つかりません。先に findy_scraper/cli.py を実行してください。")
        return None
    except json.JSONDecodeError:
        logging.error(f"{CACHE_FILE} のJSON形式が正しくありません。")
        return None
    except Exception as e:
        logging.error(f"ファイル読み込み中にエラーが発生しました: {e}")
        return None 