import os
import json
import logging # logging を使うように修正
from typing import Optional # Optional をインポート
from openai import AsyncOpenAI

# 環境変数からAPIキー、対象フィールド、モデル名を取得
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL_NAME = os.getenv('OPENAI_MODEL_NAME', 'gpt-4o-mini') # デフォルトを設定
OPENAI_TARGET_FIELDS_STR = os.getenv('OPENAI_TARGET_FIELDS')

# デフォルトのターゲットフィールドリスト
DEFAULT_TARGET_FIELDS = [
    "会社名", "URL", "状況", "選考プロセス (ステップ概要)", "職種",
    "事業ドメイン/業界", "社員数", "生成AI", "給与下限(万)", "給与上限(万)",
    "主な職務内容", "必須スキル/経験 (要約)", "歓迎スキル/経験 (要約)",
    "使用技術 (主要)", "勤務地", "リモートワーク", "フレックス (コアタイム)",
    "福利厚生 (特筆事項)", "仕事の魅力/アピール内容 (要約)",
    "求める人物像 (要約)", "特記事項"
]

# 環境変数からフィールドリストを生成、なければデフォルトを使用
if OPENAI_TARGET_FIELDS_STR:
    try:
        TARGET_FIELDS = [field.strip() for field in OPENAI_TARGET_FIELDS_STR.split(',') if field.strip()]
        logging.info(f"環境変数からターゲットフィールドを読み込みました: {len(TARGET_FIELDS)} 件")
    except Exception as e:
        logging.warning(f"環境変数 OPENAI_TARGET_FIELDS のパースに失敗しました。デフォルト値を使用します。エラー: {e}")
        TARGET_FIELDS = DEFAULT_TARGET_FIELDS
else:
    logging.info("環境変数 OPENAI_TARGET_FIELDS が未設定のため、デフォルト値を使用します。")
    TARGET_FIELDS = DEFAULT_TARGET_FIELDS

async def analyze_job_page_with_gpt(page_text_content: str, job_title: str, job_link: str) -> Optional[dict]:
    if not OPENAI_API_KEY:
        logging.error("エラー: OPENAI_API_KEYが設定されていません。LLM分析をスキップします。")
        return {"元タイトル": job_title, "元リンク": job_link, "エラー": "APIキー未設定"}

    logging.info(f"  [{job_title}] LLM ({OPENAI_MODEL_NAME}) によるページテキスト解析を開始...")

    # OpenAIクライアントの初期化
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    user_prompt = f"""
以下の求人ページのテキストコンテンツから、指定された項目を抽出し、JSON形式で回答してください。
項目が存在しない場合は、null または "該当なし" としてください。
URLは必ず抽出してください。存在しない場合は元のURL `{job_link}` を使用してください。
会社名は必ず抽出してください。存在しない場合はタイトル `{job_title}` から推測するか、「会社名不明」としてください。
回答はJSONオブジェクトのみを出力してください。マークダウンの ```json ... ``` は不要です。

求人タイトル: 「{job_title}」
求人URL: 「{job_link}」

抽出項目:
{json.dumps(TARGET_FIELDS, ensure_ascii=False, indent=2)}

解析対象テキスト:
---
{page_text_content[:20000]} 
---
(テキストは情報量を増やすため先頭20000文字を使用)

JSON出力:
"""

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL_NAME, # 環境変数から取得したモデル名を使用
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=180
        )

        result_json_str = response.choices[0].message.content
        logging.info(f"  [{job_title}] LLM解析完了。")

        try:
            analysis_result = json.loads(result_json_str)

            analysis_result["元タイトル"] = job_title
            analysis_result["元リンク"] = job_link

            if "URL" not in analysis_result or not analysis_result["URL"]:
                analysis_result["URL"] = job_link
                logging.warning(f"  [{job_title}] 警告: LLMがURLを抽出できなかったため、元のリンクを使用します。")
            if "会社名" not in analysis_result or not analysis_result["会社名"]:
                 analysis_result["会社名"] = job_title
                 logging.warning(f"  [{job_title}] 警告: LLMが会社名を抽出できなかったため、元のタイトルを使用します。")

            return analysis_result
        except json.JSONDecodeError as json_error:
            logging.error(f"  [{job_title}] LLM応答のJSONパースに失敗: {json_error}")
            logging.debug(f"  LLM応答内容(先頭500文字): {result_json_str[:500]}...")
            return {"元タイトル": job_title, "元リンク": job_link, "エラー": f"LLM応答パース失敗: {json_error}", "LLM応答": result_json_str}
        except Exception as parse_err:
             logging.error(f"  [{job_title}] LLM応答の処理中にエラー: {parse_err}")
             return {"元タイトル": job_title, "元リンク": job_link, "エラー": f"LLM応答処理エラー: {parse_err}", "LLM応答": result_json_str}

    except Exception as e:
        error_message = f"LLM API呼び出しエラー: {e}"
        logging.error(f"  [{job_title}] {error_message}")
        return {"元タイトル": job_title, "元リンク": job_link, "エラー": error_message} 