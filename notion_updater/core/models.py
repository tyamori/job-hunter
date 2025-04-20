# --- 自動作成するNotionデータベースのプロパティ定義 ---
# プロパティ名: { "type": "notion_type", "config": { ... } }
# config は type ごとに異なる (例: number の format, select の options)
# "rename_target": True は既存の Title プロパティをこの名前に変更することを示す
DESIRED_PROPERTIES_SCHEMA = {
    "会社名": {"type": "title", "config": {}, "rename_target": True}, # Title
    "URL": {"type": "url", "config": {}}, # URL (PK)
    "状況": {"type": "rich_text", "config": {}}, # Select -> Rich Text
    "選考プロセス": {"type": "rich_text", "config": {}}, # Text
    "職種": {"type": "rich_text", "config": {}}, # Select -> Rich Text
    "事業ドメイン/業界": {"type": "rich_text", "config": {}}, # Select -> Rich Text
    "社員数": {"type": "rich_text", "config": {}}, # Numberだと '該当なし' 等扱えないためText
    "生成AI": {"type": "rich_text", "config": {}}, # Select -> Rich Text
    "給与下限(万)": {"type": "number", "config": {"format": "number"}}, # Number
    "給与上限(万)": {"type": "number", "config": {"format": "number"}}, # Number
    "主な職務内容": {"type": "rich_text", "config": {}}, # Text
    "必須スキル/経験": {"type": "rich_text", "config": {}}, # Text
    "歓迎スキル/経験": {"type": "rich_text", "config": {}}, # Text
    "使用技術": {"type": "multi_select", "config": {"options": []}}, # Multi-select
    "勤務地": {"type": "rich_text", "config": {}}, # Text (構造化は複雑なので一旦Text)
    "リモートワーク": {"type": "rich_text", "config": {}}, # Select -> Rich Text
    "フレックス": {"type": "rich_text", "config": {}}, # Text (コアタイムなど)
    "福利厚生": {"type": "rich_text", "config": {}}, # Text
    "仕事の魅力": {"type": "rich_text", "config": {}}, # Text
    "求める人物像": {"type": "rich_text", "config": {}}, # Text
    "特記事項": {"type": "rich_text", "config": {}}, # Text
    "最終更新日時": {"type": "date", "config": {}}, # Date (スクリプトが設定)
    # --- 手動入力項目 (列だけ作成) ---
    "メモ": {"type": "rich_text", "config": {}}, # Text
    "技術力": {"type": "rich_text", "config": {}}, # Select -> Rich Text
}

# --- 更新時に除外する手動入力項目 ---
MANUAL_UPDATE_EXCLUDE_PROPS = {"メモ", "技術力"}

# スクリプト <-> Notion間のキーマッピング (基本的には同じ名前を使う)
# ここでは DESIRED_PROPERTIES_SCHEMA のキーをそのまま使う想定
PROPERTY_MAP = {prop_name: prop_name for prop_name in DESIRED_PROPERTIES_SCHEMA}
# JSON側のキー名が異なる場合はここでマッピングを調整
PROPERTY_MAP.update({
    "選考プロセス": "選考プロセス (ステップ概要)",
    "必須スキル/経験": "必須スキル/経験 (要約)",
    "歓迎スキル/経験": "歓迎スキル/経験 (要約)",
    "使用技術": "使用技術 (主要)",
    "フレックス": "フレックス (コアタイム)",
    "福利厚生": "福利厚生 (特筆事項)",
    "仕事の魅力": "仕事の魅力/アピール内容 (要約)",
    "求める人物像": "求める人物像 (要約)",
}) 