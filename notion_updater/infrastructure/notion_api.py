import logging
import json
import asyncio
from notion_client import AsyncClient, APIResponseError, APIErrorCode
from notion_updater.core.models import DESIRED_PROPERTIES_SCHEMA # 相対インポートに変更

# --- Notionデータベース スキーマ管理 ---

async def ensure_database_schema(client: AsyncClient, database_id: str):
    logging.info(f"データベースID: {database_id} のスキーマを確認・更新します...")
    try:
        db_info = await client.databases.retrieve(database_id=database_id)
        existing_properties = db_info.get("properties", {})
        logging.info(f"既存のプロパティを {len(existing_properties)} 件取得しました。")
        # print(json.dumps(existing_properties, ensure_ascii=False, indent=2)) # デバッグ用

        properties_to_update = {}
        title_prop_id_to_rename = None
        current_title_prop_name = None

        # 1. Titleプロパティの確認とリネーム準備
        desired_title_name = next((k for k, v in DESIRED_PROPERTIES_SCHEMA.items() if v.get("rename_target")), None)
        if desired_title_name:
            found_title = False
            for prop_name, prop_data in existing_properties.items():
                if prop_data.get("type") == "title":
                    current_title_prop_name = prop_name
                    title_prop_id_to_rename = prop_data.get("id") # IDを取得
                    if prop_name != desired_title_name:
                        logging.info(f"既存のTitleプロパティ '{prop_name}' を '{desired_title_name}' にリネームします。")
                        # リネームは properties_to_update で行う (新しい名前で定義)
                        properties_to_update[desired_title_name] = {"name": desired_title_name, "title": {}}
                    else:
                         logging.info(f"Titleプロパティ '{desired_title_name}' は既に存在します。")
                    found_title = True
                    break
            if not found_title:
                 logging.error("データベースにTitleプロパティが見つかりません。これは通常発生しません。")
                 # Titleプロパティは update API では追加できないためエラーとする
                 return None

        # 2. その他の必須・任意プロパティの確認と作成準備
        for prop_name, schema in DESIRED_PROPERTIES_SCHEMA.items():
            # Titleプロパティは上で処理済みorリネーム対象なのでスキップ
            if schema.get("rename_target"):
                continue

            if prop_name not in existing_properties:
                logging.info(f"プロパティ '{prop_name}' (タイプ: {schema['type']}) が存在しないため、作成します。")
                properties_to_update[prop_name] = {
                    "name": prop_name, # nameフィールドも必要
                    schema['type']: schema['config'] # typeに応じたconfigを設定
                }
            else:
                # 型が異なる場合の処理を追加
                 existing_prop_data = existing_properties[prop_name]
                 existing_type = existing_prop_data.get("type")
                 desired_type = schema["type"]
                 if existing_type != desired_type:
                      logging.warning(f"プロパティ '{prop_name}' の型が異なります。期待: {desired_type}, 実際: {existing_type}。型変更を試みます。")
                      # 型変更を試みるために update リクエストに含める
                      # Note: 型変更が常に成功するとは限らない。特にデータが存在する場合。
                      # config も含めて上書きする形で指定する
                      properties_to_update[prop_name] = {
                          "name": prop_name, # 型変更時も name が必要な場合がある
                          desired_type: schema['config']
                      }
                 # else: 型が一致する場合は何もしない

        # 3. プロパティの更新が必要な場合、APIを呼び出す
        if properties_to_update:
            logging.info(f"{len(properties_to_update)} 件のプロパティを作成・更新します...")
            # print(json.dumps({"properties": properties_to_update}, indent=2)) # デバッグ用
            try:
                await client.databases.update(
                    database_id=database_id,
                    properties=properties_to_update
                )
                logging.info("データベーススキーマの更新に成功しました。")
                # 更新後のスキーマを再取得
                db_info = await client.databases.retrieve(database_id=database_id)
                existing_properties = db_info.get("properties", {})
                logging.info("更新後のスキーマ情報を取得しました。")
            except APIResponseError as api_error:
                logging.error(f"データベーススキーマの更新中にAPIエラーが発生しました: {api_error}")
                logging.error(f"送信したデータ: {json.dumps({'properties': properties_to_update}, indent=2)}")
                return None # エラー時はNoneを返す
            except Exception as e:
                 logging.error(f"データベーススキーマの更新中に予期せぬエラー: {e}")
                 return None
        else:
            logging.info("既存のプロパティは全て期待通りです。スキーマ更新は不要です。")

        return existing_properties # 更新後(または元々問題なかった)のプロパティ情報を返す

    except APIResponseError as e:
        if e.code == APIErrorCode.ObjectNotFound:
             logging.error(f"指定されたデータベースID '{database_id}' が見つかりません。")
        elif e.code == APIErrorCode.Unauthorized:
             logging.error(f"Notion APIキーが無効または権限がありません。インテグレーションに必要な権限（DB編集含む）が付与されているか確認してください。")
        elif e.code == APIErrorCode.RateLimited:
             logging.error(f"Notion APIのレートリミットに達しました。しばらく待って再試行してください。")
        else:
             logging.error(f"データベース情報取得中にAPIエラーが発生しました: {e}")
        return None
    except Exception as e:
        logging.error(f"データベース情報取得中に予期せぬエラーが発生しました: {e}")
        return None

# Notionデータベースから既存の求人URLとページIDを取得する関数
async def get_existing_notion_pages(client: AsyncClient, database_id: str, url_property_name: str) -> dict[str, str] | None:
    existing_pages = {}
    logging.info("Notionデータベースから既存の求人ページ (URL->ID) を取得中...")
    if not url_property_name:
         logging.error("URLプロパティ名が指定されていません。")
         return None

    try:
        has_more = True
        next_cursor = None
        page_count = 0
        while has_more:
            response = await client.databases.query(
                database_id=database_id,
                filter={ # 指定されたURLプロパティが存在するものだけを対象
                    "property": url_property_name,
                    "url": {
                        "is_not_empty": True
                    }
                },
                page_size=100,
                start_cursor=next_cursor
            )
            results = response.get('results', [])
            page_count += len(results)
            for page in results:
                url_prop = page.get('properties', {}).get(url_property_name, {})
                if url_prop and url_prop.get('url'):
                    page_id = page.get('id')
                    if page_id:
                         existing_pages[url_prop['url']] = page_id

            has_more = response.get('has_more', False)
            next_cursor = response.get('next_cursor')
            if has_more:
                 logging.info(f"  ... {len(existing_pages)} 件取得済み (現在ページ {page_count} 件)、次のページを取得中 ...")
                 await asyncio.sleep(0.35) # Rate limit対策 (少し長めに)

        logging.info(f"既存のページ情報を {len(existing_pages)} 件取得しました。")
        return existing_pages
    except APIResponseError as e:
        # URLプロパティが見つからない場合のエラーハンドリングを追加
        if e.code == APIErrorCode.ValidationFailed and f'property "{url_property_name}" does not exist' in str(e.body):
             logging.error(f"データベースに '{url_property_name}' という名前のURLプロパティが見つかりません。スキーマ自動更新が正しく機能したか確認してください。")
        else:
             logging.error(f"NotionデータベースからのURL取得中にAPIエラーが発生しました: {e}")
        return None
    except Exception as e:
        logging.error(f"NotionデータベースからのURL取得中に予期せぬエラーが発生しました: {e}")
        return None

# Notionに新しいページを作成する関数
async def create_notion_page(client: AsyncClient, database_id: str, properties: dict):
    # Titleプロパティ名を取得してログに出力
    title_prop_name = next((k for k, v in properties.items() if 'title' in v), None)
    page_title = "タイトル不明"
    if title_prop_name and properties[title_prop_name]['title']:
         page_title = properties[title_prop_name]['title'][0]['text']['content']

    logging.info(f"  Notionに新規ページ作成中: {page_title}")
    try:
        await client.pages.create(
            parent={"database_id": database_id},
            properties=properties
        )
        logging.info("  ...作成成功")
        await asyncio.sleep(0.55) # Rate limit対策 (少し長めに)
        return True
    except APIResponseError as e:
        logging.error(f"  Notionページ作成中にAPIエラーが発生しました: {e}")
        logging.error(f"  エラーコード: {e.code}")
        try:
            # エラーレスポンスのbodyをJSONとしてパース試行
            error_body = json.loads(e.body)
            logging.error(f"  エラー詳細: {json.dumps(error_body, ensure_ascii=False, indent=2)}")
        except json.JSONDecodeError:
            logging.error(f"  エラーメッセージ (raw): {e.body}")
        # 失敗したプロパティ内容もログに出力 (長すぎる可能性に注意)
        # logging.error(f"  送信したプロパティ: {json.dumps(properties, ensure_ascii=False, indent=2)}")
        return False
    except Exception as e:
        logging.error(f"  Notionページ作成中に予期せぬエラーが発生しました: {e}")
        return False

# Notionの既存ページを更新する関数
async def update_notion_page(client: AsyncClient, page_id: str, properties: dict, exclude_props: set):
    # 更新対象プロパティから除外対象を除き、最終更新日時を強制的に含める
    properties_to_update = {
        k: v for k, v in properties.items()
        if k not in exclude_props or k == "最終更新日時"
    }

    if not properties_to_update:
        logging.info(f"  ページID: {page_id} - 更新対象のプロパティがありません。スキップします。")
        return True # 更新不要も成功とみなす

    # Titleプロパティ名を取得してログに出力
    title_prop_name = next((k for k, v in properties_to_update.items() if 'title' in v), None)
    page_title = "(タイトル不明または更新対象外)"
    if title_prop_name and properties_to_update[title_prop_name]['title']:
         page_title = properties_to_update[title_prop_name]['title'][0]['text']['content']

    logging.info(f"  Notionの既存ページ更新中: {page_title} (ID: {page_id})")
    # logging.debug(f"  送信するプロパティ: {json.dumps(properties_to_update, ensure_ascii=False, indent=2)}")

    try:
        await client.pages.update(
            page_id=page_id,
            properties=properties_to_update
        )
        logging.info("  ...更新成功")
        await asyncio.sleep(0.55) # Rate limit対策 (少し長めに)
        return True
    except APIResponseError as e:
        logging.error(f"  Notionページ更新中にAPIエラーが発生しました (Page ID: {page_id}): {e}")
        logging.error(f"  エラーコード: {e.code}")
        try:
            error_body = json.loads(e.body)
            logging.error(f"  エラー詳細: {json.dumps(error_body, ensure_ascii=False, indent=2)}")
        except json.JSONDecodeError:
            logging.error(f"  エラーメッセージ (raw): {e.body}")
        return False
    except Exception as e:
        logging.error(f"  Notionページ更新中に予期せぬエラーが発生しました (Page ID: {page_id}): {e}")
        return False 