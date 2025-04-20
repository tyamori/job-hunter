import logging
from datetime import datetime
from .models import PROPERTY_MAP

# Notionのデータ型に応じて値をフォーマットする関数
def format_notion_value(key: str, value: any, db_properties: dict):
    prop_config = db_properties.get(key)
    if not prop_config:
        logging.warning(f"プロパティ '{key}' のスキーマ情報が見つかりません。フォーマットをスキップします。")
        return None

    prop_type = prop_config['type']

    if value is None or value == "該当なし":
        return None # 空の値は設定しない

    try:
        if prop_type == 'title':
            return [{"type": "text", "text": {"content": str(value)[:2000]}}]
        elif prop_type == 'rich_text':
            return [{"type": "text", "text": {"content": str(value)[:2000]}}]
        elif prop_type == 'number':
            if isinstance(value, str):
                 # 数字、小数点、マイナス記号以外を除去してから変換 (より頑健に)
                 cleaned_value = ''.join(filter(lambda x: x.isdigit() or x == '.' or (x == '-' and value.startswith('-')), str(value)))
                 if not cleaned_value: return None
                 return float(cleaned_value)
            elif isinstance(value, (int, float)):
                 return float(value)
            else:
                 raise ValueError("Invalid number format")
        elif prop_type == 'url':
            # 簡易的なURL形式チェック
            return str(value) if isinstance(value, str) and value.startswith('http') and len(value) < 2001 else None
        elif prop_type == 'select':
            # Select/Multi-selectのoption名は100文字制限
            return {"name": str(value)[:100]} if value else None
        elif prop_type == 'multi_select':
            options = []
            if isinstance(value, list):
                options = [{"name": str(v)[:100]} for v in value if v is not None]
            elif isinstance(value, str):
                 options = [{"name": v.strip()[:100]} for v in value.split(',') if v.strip()]
            # Multi-select は空リストでも有効
            return options
        elif prop_type == 'date':
             # スクリプト実行日の日付のみを設定
             return {"start": datetime.now().strftime('%Y-%m-%d')}
        elif prop_type == 'checkbox':
             return bool(value)
        else:
            logging.warning(f"未対応または不明なプロパティタイプ '{prop_type}' (プロパティ: {key})。rich_textとして扱います。")
            return [{"type": "text", "text": {"content": str(value)[:2000]}}]
    except Exception as e:
        logging.warning(f"値のフォーマット中にエラー (プロパティ: {key}, タイプ: {prop_type}, 値: {value}): {e}")
        return None

# JSONデータをNotionプロパティ形式に変換する関数
def convert_to_notion_properties(job_data: dict, db_properties: dict) -> dict:
    properties = {}
    # PROPERTY_MAP のキー (Notionプロパティ名) を基準にループ
    for notion_prop, json_key in PROPERTY_MAP.items():
        # 最終更新日時は特別扱い (JSONに無くても生成)
        if notion_prop == "最終更新日時":
            value = datetime.now().strftime('%Y-%m-%d')
        elif json_key in job_data:
            value = job_data.get(json_key)
        else:
            continue # JSONに対応するキーがなければスキップ

        # Notion DBにプロパティが存在するか再確認
        if notion_prop not in db_properties:
            logging.warning(f"変換対象のプロパティ '{notion_prop}' がDBスキーマに存在しません。スキップします。")
            continue

        formatted_value = format_notion_value(notion_prop, value, db_properties)

        if formatted_value is not None:
            prop_type = db_properties[notion_prop]['type']
            # Date型はキーが異なる
            if prop_type == 'date':
                 properties[notion_prop] = {"date": formatted_value}
            else:
                properties[notion_prop] = {prop_type: formatted_value}
        # else: # フォーマット結果がNoneの場合は何も設定しない
        #     logging.debug(f"プロパティ '{notion_prop}' の値がNoneのため設定しません。元値: {value}")

    # 必須プロパティ(Title, URL)の存在チェックを追加
    title_prop_name = next((k for k, v in db_properties.items() if v['type'] == 'title'), None)
    url_prop_name = "URL" # 固定

    if title_prop_name not in properties:
        logging.error(f"必須プロパティ '{title_prop_name}' が変換後のデータに含まれていません。")
        # 必要であれば空のタイトルを設定するなどのフォールバック処理
        # properties[title_prop_name] = {"title": [{"type": "text", "text": {"content": "タイトル不明"}}]}
    if url_prop_name not in properties:
        logging.error(f"必須プロパティ '{url_prop_name}' が変換後のデータに含まれていません。")
        # URLがないとページを識別できないため、このページの登録は失敗する可能性が高い

    return properties 