import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext, Playwright

BASE_URL = "https://findy-code.io"

# === Playwrightヘルパー関数 ===

async def login_findy(page: Page, email: str, password: str):
    print("Findyにアクセスしています...")
    await page.goto(f'{BASE_URL}/home')
    print("ログインページに移動しています...")
    try:
        # ログインボタンが表示されるまで待つ (最大10秒)
        await page.locator('text=ログイン').wait_for(timeout=10000)
        await page.click('text=ログイン')
    except Exception:
        # すでにログインページにいるか、レイアウトが変更された可能性
        print("ログインボタンが見つかりません。現在のURLでログイン試行します。")
        # ログインフォームが表示されるまで待つ (より堅牢に)
        try:
             await page.locator('input[name="email"]').wait_for(timeout=10000)
        except Exception as form_error:
             print(f"ログインフォームの検出に失敗しました: {form_error}")
             await page.screenshot(path='login_form_error.png')
             raise Exception("ログインフォームが見つかりません。Findyのページ構成が変更された可能性があります。")
        
    print("ログイン情報を入力しています...")
    await page.fill('input[name="email"]', email)
    await page.fill('input[name="password"]', password)
    print("ログインしています...")
    try:
        # ナビゲーションを待機 (タイムアウトを60秒に延長)
        async with page.expect_navigation(timeout=60000):
            await page.click('button[type="submit"]')
        # ログイン後の特定の要素を確認 (例: 自分のアイコンやホーム画面の要素)
        # await page.locator('[data-testid="user-menu"]').wait_for(timeout=15000)
        print("ログイン成功")
    except Exception as nav_error:
        print(f"ログイン後のナビゲーションまたは要素確認に失敗しました: {nav_error}")
        await page.screenshot(path='login_navigation_error.png')
        # ログイン失敗の可能性を示す例外を発生させる
        raise Exception(f"ログイン失敗の可能性があります: {nav_error}")

async def scrape_likes_page_links(page: Page) -> list[dict]:
    print(f"現在のページからリンクを収集中: {page.url}")
    job_link_data = []
    # セレクターをより具体的に (Findyの構造が変わる可能性を考慮)
    job_listings_selector = 'a[href^="/companies/"][href*="/jobs/"]' # 求人詳細へのリンクと仮定
    try:
        # 要素が表示されるまで少し待つ
        await page.locator(job_listings_selector).first.wait_for(timeout=15000)
        job_listings = await page.query_selector_all(job_listings_selector)
    except Exception as e:
         print(f"求人リンクのセレクター({job_listings_selector})が見つかりません: {e}")
         # ページの内容を出力してデバッグしやすくする
         # print(await page.content()) 
         return []
    
    if not job_listings:
        print("このページでは求人リンクが見つかりませんでした。")
        return []

    print(f"{len(job_listings)}件の求人リンク要素が見つかりました。情報を取得中...")
    for link_element in job_listings:
        job_title = await link_element.text_content() # タイトル取得を試みる
        job_link_raw = await link_element.get_attribute('href')
        job_link = "不明"
        
        if job_link_raw:
            if job_link_raw.startswith('/'):
                job_link = f"{BASE_URL}{job_link_raw}"
            else:
                job_link = job_link_raw 
        
        # 有効なリンクを持つものだけを追加
        if job_link != "不明":
            job_link_data.append({
                "title": job_title.strip() if job_title else "タイトル不明", 
                "link": job_link
            })
        # else: # デバッグ用
        #     print(f"  無効なリンクをスキップ: raw='{job_link_raw}'")
            
    print(f"{len(job_link_data)}件の有効な求人リンクを取得しました。")
    return job_link_data

async def get_all_liked_job_links(page: Page) -> list[dict]:
    print("\n--- いいねページの全リンク収集開始 ---")
    await page.goto(f'{BASE_URL}/likes')
    # ネットワークが安定するまで待つ + 少し追加で待つ
    await page.wait_for_load_state('networkidle', timeout=30000) 
    await page.wait_for_timeout(1000)

    all_job_links_info = []
    page_num = 1
    processed_urls = set() # 処理済みページURLを記録

    while True:
        current_url = page.url
        if current_url in processed_urls:
            print(f"警告: ページループを検出しました ({current_url})。収集を終了します。")
            break
        processed_urls.add(current_url)
        
        print(f"--- リンク収集: ページ {page_num} ({current_url}) --- ")
        # ページが完全に表示されるのを待つ（動的コンテンツ対策）
        await page.wait_for_timeout(1500) 
        page_links_info = await scrape_likes_page_links(page)
        all_job_links_info.extend(page_links_info)
        
        # 次へボタンのセレクターを特定
        next_page_selector = 'ul.pagination_component_pagination__h4ax6 li:not(.disabled) a:has-text("次へ")'
        next_page_link = page.locator(next_page_selector)
        
        try:
            # 「次へ」ボタンが存在し、クリック可能か確認 (タイムアウトを短めに設定)
            await next_page_link.wait_for(state='visible', timeout=5000)
            
            next_page_url_raw = await next_page_link.get_attribute('href')
            if next_page_url_raw:
                next_page_url = f"{BASE_URL}{next_page_url_raw}" if next_page_url_raw.startswith('/') else next_page_url_raw
                print(f"次のページへ移動: {next_page_url}")
                # ナビゲーションを待機
                async with page.expect_navigation(wait_until='networkidle', timeout=30000):
                    await next_page_link.click()
                await page.wait_for_timeout(1000) # 遷移後の安定待ち
                page_num += 1
            else: 
                print("次のページのhref属性が取得できませんでした。")
                break
        except Exception as e:
            # タイムアウトは「次へ」ボタンがないことを意味する可能性が高い
            if "Timeout" in str(e):
                print("次のページリンクが見つかりません。リンク収集完了。")
            else:
                 print(f"次のページへの遷移中にエラー: {e}")
            break
            
    # 重複をリンクで除去
    unique_links_info = list({info['link']: info for info in all_job_links_info if info['link'] != "不明"}.values())
    print(f"\n--- 合計 {len(unique_links_info)} 件のユニークな求人リンクを収集しました --- ")
    return unique_links_info

async def get_job_page_content(page: Page, job_link: str, job_title: str) -> str | None:
    print(f"テキスト取得中: {job_title} ({job_link})")
    try:
        # ページの遷移と読み込み完了を待つ (タイムアウトを延長)
        await page.goto(job_link, wait_until='networkidle', timeout=90000) 
        await page.wait_for_timeout(1000) # 念のため少し待つ
        
        # body全体のテキストを取得 (より多くの情報を取得)
        page_text_content = await page.locator('body').inner_text(timeout=30000) # タイムアウトを30秒に設定
        print("  表示テキスト取得完了")
        return page_text_content
    except Exception as page_error:
        print(f"  詳細ページのアクセスまたはテキスト取得中にエラー: {page_error}")
        try:
             await page.screenshot(path=f'error_page_{job_title[:20]}.png') # エラー時のスクショ
             print(f"  エラー時のスクリーンショットを保存: error_page_{job_title[:20]}.png")
        except Exception as ss_error:
             print(f"  スクリーンショットの保存に失敗: {ss_error}")
        return None # エラー時はNoneを返す

# Playwrightの起動とブラウザ操作のコンテキストマネージャ
class PlaywrightManager:
    def __init__(self, headless: bool = True):
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: BrowserContext | None = None

    async def __aenter__(self):
        print("Playwrightを起動しています...")
        self._playwright = await async_playwright().start()
        print("ブラウザを起動しています... (headless={})", self._headless)
        browser_instance = await self._playwright.chromium.launch(headless=self._headless)
        self._browser = await browser_instance.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36' # 一般的なUA
        )
        print("新しいページを作成しています...")
        page = await self._browser.new_page()
        return page # ページオブジェクトを返す

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("ブラウザコンテキストを閉じています...")
        if self._browser:
            await self._browser.close()
        print("Playwrightを停止しています...")
        if self._playwright:
            await self._playwright.stop()
        print("Playwright関連のリソースを解放しました。")
        if exc_type:
            print(f"Playwright処理中にエラーが発生しました: {exc_val}")
        # エラーを再送出しない場合は False を返す
        return False 