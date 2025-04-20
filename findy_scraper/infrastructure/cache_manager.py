import os
import json
import logging # loggingを使うように修正

CACHE_DIR = ".cache" # キャッシュディレクトリ名
CACHE_FILE_NAME = "analyzed_findy_jobs.json"
CACHE_FILE = os.path.join(CACHE_DIR, CACHE_FILE_NAME)

# キャッシュをロードする関数
def load_cache(force_reload: bool) -> dict:
    cached_results = {}
    if os.path.exists(CACHE_FILE) and not force_reload:
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cached_data_list = json.load(f)
                # URL(元リンク)をキーにした辞書を作成
                for item in cached_data_list:
                    link = item.get("URL") or item.get("元リンク")
                    if link:
                        cached_results[link] = item
            logging.info(f"キャッシュファイルを読み込みました: {CACHE_FILE} ({len(cached_results)} 件)")
        except Exception as e:
            logging.warning(f"キャッシュファイル ({CACHE_FILE}) の読み込みに失敗しました: {e}")
            cached_results = {}
    else:
        if force_reload:
            logging.info("--force-reload オプションによりキャッシュを無視します。")
        elif not os.path.exists(CACHE_FILE):
            logging.info(f"キャッシュファイル {CACHE_FILE} が見つかりません。")
        # 他の理由でパスが存在しない場合も考慮 (ディレクトリでないなど)
        elif not os.path.isfile(CACHE_FILE):
             logging.warning(f"キャッシュパス {CACHE_FILE} はファイルではありません。")

    return cached_results

# 結果をキャッシュに保存する関数
def save_cache(results_dict: dict):
    try:
        # キャッシュディレクトリが存在しない場合は作成
        if not os.path.exists(CACHE_DIR):
            logging.info(f"キャッシュディレクトリ {CACHE_DIR} が存在しないため作成します。")
            os.makedirs(CACHE_DIR, exist_ok=True)
        elif not os.path.isdir(CACHE_DIR):
             logging.error(f"キャッシュパス {CACHE_DIR} はディレクトリではありません。保存できません。")
             return

        # 辞書の値をリストに変換して保存
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(results_dict.values()), f, ensure_ascii=False, indent=2)
        logging.info(f"解析結果を {CACHE_FILE} に保存しました。")
    except Exception as e:
        logging.error(f"キャッシュファイル ({CACHE_FILE}) の保存に失敗しました: {e}") 