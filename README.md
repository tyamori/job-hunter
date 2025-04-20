# Findy いいね解析 & Notion連携ツール

Findyでの転職活動をサポートするツールです。Findyにログインして「いいね」された求人情報を取得・解析し、Notionデータベースに自動で登録・更新します。

## 機能概要

このプロジェクトは主に2つのスクリプト（パッケージ）で構成されます。

1.  **`findy_scraper`**: 
    *   Findyにログインします。
    *   「いいね」された求人のURLとタイトルを取得します。
    *   各求人ページの詳細情報を取得します。
    *   LLM (OpenAI API) を利用して、求人情報を構造化データに解析します。
    *   解析結果を `analyzed_findy_jobs.json` にキャッシュとして保存します。
2.  **`notion_updater`**: 
    *   `analyzed_findy_jobs.json` から解析済み求人データを読み込みます。
    *   指定されたNotionデータベースのスキーマ（プロパティ）を自動で確認・作成・更新します。
    *   求人データをNotionデータベースに登録します。
    *   既存の求人データは（手動入力項目を除き）更新します。

## ディレクトリ構成

```
job_hunter/
├── findy_scraper/         # Findyスクレイピング関連
│   ├── application/         # メインロジック
│   ├── infrastructure/    # Playwright, LLM, Cache連携
│   └── cli.py               # 実行スクリプト
├── notion_updater/        # Notion連携関連
│   ├── application/         # メインロジック
│   ├── core/              # データ構造、フォーマット
│   ├── infrastructure/    # Notion API, ファイルI/O
│   └── cli.py               # 実行スクリプト
├── .env                   # 環境変数ファイル
├── .env.example           # 環境変数ファイル例
├── analyzed_findy_jobs.json # 解析結果キャッシュ (Git管理外)
├── pyproject.toml         # プロジェクト設定、依存関係
└── README.md              # このファイル
```

## 必要条件

- Python 3.8以上
- Rye (推奨されるパッケージ管理ツール)
- OpenAI APIキー
- Notion APIキーとデータベースID

## セットアップ

### 1. Ryeのインストール（未導入の場合）

```bash
curl -sSf https://rye.astral.sh/get | bash
# シェルを再起動するか、指示に従ってPATHを通してください
```

### 2. プロジェクトのセットアップと依存関係のインストール

```bash
# プロジェクトディレクトリに移動
cd job-hunter 

# Ryeに必要な設定と依存関係をインストール
rye sync 
```

### 3. Playwright ブラウザのインストール

```bash
# Ryeが管理する仮想環境内で実行
rye run playwright install
```

### 4. 環境変数の設定

`.env.example` をコピーして `.env` ファイルを作成し、必要な情報を設定します。

```bash
cp .env.example .env
```

`.env` ファイルを開き、以下の項目を編集してください：

```dotenv
# Findy ログイン情報
FINDY_EMAIL=あなたのFindyメールアドレス
FINDY_PASSWORD=あなたのFindyパスワード

# OpenAI APIキーと設定
OPENAI_API_KEY=あなたのOpenAI APIキー
# 使用するモデル名 (例: gpt-4o, gpt-4o-mini, gpt-3.5-turbo)
OPENAI_MODEL_NAME=gpt-4o-mini
# LLMに抽出させる項目 (カンマ区切り、スペースはトリムされます。未設定の場合はデフォルト値が使用されます)
OPENAI_TARGET_FIELDS=会社名,URL,状況,選考プロセス (ステップ概要),職種,...

# Notion 設定
NOTION_API_KEY=あなたのNotionインテグレーションAPIキー
# 対象のNotionデータベースID (URLの https://www.notion.so/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=... の xxxxx 部分)
NOTION_DATABASE_ID=あなたのNotionデータベースID 
```

**Notionの設定補足:**

*   **インテグレーション作成:** Notionの[インテグレーション設定ページ](https://www.notion.so/my-integrations)で新しいインテグレーションを作成し、「シークレット」APIキーを取得します。
*   **データベース共有:** 対象のNotionデータベースを開き、右上の「共有」メニューから作成したインテグレーションを選択し、「編集権限あり」で招待します。
*   **データベースID:** 対象データベースのURLからIDを取得します。

## 使い方

以下のコマンドをプロジェクトルートで実行します。
Ryeを使用している場合、`rye run` を先頭につけます。

**1. Findyから情報を取得・解析:**

```bash
rye run python findy_scraper/cli.py
```

*   キャッシュを無視して強制的に再取得・再解析する場合は `--force-reload` オプションを追加します。
    ```bash
    rye run python findy_scraper/cli.py --force-reload
    ```
*   実行時にブラウザの動作を確認したい場合は `--no-headless` オプションを追加します。
    ```bash
    rye run python findy_scraper/cli.py --no-headless
    ```

**2. 解析結果をNotionに登録・更新:**

```bash
rye run python notion_updater/cli.py
```

このスクリプトは、初回実行時にNotionデータベースに必要なプロパティを自動で作成・更新します。2回目以降は `analyzed_findy_jobs.json` の内容に基づいてNotionのページを追加・更新します。

## 注意事項

- **Findyのサイト構造変更:** FindyのWebサイトの構造が変更されると、`findy_scraper` のセレクタ等が機能しなくなる可能性があります。エラーが発生した場合は `findy_scraper/infrastructure/playwright_handler.py` 内のセレクタの修正が必要になることがあります。
- **APIキーの管理:** `.env` ファイルに記述したAPIキー等は機密情報です。Gitリポジトリに誤ってコミットしないように注意してください (`.gitignore` には含まれています)。
- **LLMのコスト:** `findy_scraper` は求人情報の解析にOpenAI APIを使用します。処理する求人数に応じてコストが発生します。
- **Notion APIのレート制限:** 大量のデータを一度に処理すると、Notion APIのレート制限に達する可能性があります。スクリプト内である程度の待機処理を入れていますが、問題が発生する場合は調整が必要になることがあります。 