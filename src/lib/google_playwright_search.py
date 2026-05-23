# Playwright ile Organik Google Arama
# Organic Google Search with Playwright (Human-Like Behavior + Stealth)

import asyncio
import random
import urllib.parse
from lib.output.consolePrint import p_error, p_info, p_warn, p_log

try:
    from playwright.sync_api import sync_playwright, Playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    p_warn(
        "Playwright not installed. Run: pip install playwright && playwright install chromium"
    )

# Stealth — Google'ın anti-bot fingerprinting'ini atlatmak için.
# Kütüphane yoksa gracefully degrade et; arama yine çalışır ama
# captcha riski artar.
try:
    from playwright_stealth import Stealth  # v2.x API
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    p_warn(
        "playwright-stealth yüklü değil. Captcha riski artar. "
        "Kurmak için: pip install playwright-stealth>=1.0.6"
    )


# Yaygın ve güncel Windows / macOS Chrome User-Agent'ları.
# Her oturum başlangıcında rastgele seçilir; tek sabit UA Google'ın
# fingerprint takibinde alarm üretebiliyor.
USER_AGENTS = [
    # Windows 10/11 + Chrome — 2024 sonu / 2025 başı sürümleri
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # macOS Apple Silicon + Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Linux Chrome (daha az sıklıkla, ama gerçek)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def human_delay(min_sec=0.5, max_sec=2.0):
    """Simulates human-like random delay."""
    import time

    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


class GooglePlaywrightSearch:
    """
    Performs organic Google searches using Playwright with human-like behavior
    + stealth fingerprint masking (playwright-stealth) to evade Google's
    anti-bot detection (navigator.webdriver, navigator.plugins, chrome runtime,
    iframe contentWindow, WebGL vendor, etc.).
    """

    def __init__(self, headless=True):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        # Her oturumda rastgele bir UA seç (sabit UA → fingerprint riski)
        self.user_agent = random.choice(USER_AGENTS)

    def init_browser(self):
        p_info("Step 1: Initializing Playwright Browser (Stealth Mode)...")
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    # Headless Chrome'da bot olarak tanınmayı azaltan ek bayraklar
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--disable-web-security",
                ],
            )

            # Realistic viewport (yaygın laptop çözünürlüğü) + rastgele UA
            p_info(f"Using rotating User-Agent: {self.user_agent[:80]}...")
            self.context = self.browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=self.user_agent,
                locale="en-US",
                timezone_id="Europe/Istanbul",
                # Permissions: gerçek bir kullanıcıdaki tipik izinler
                permissions=["geolocation"],
                # Ek HTTP başlıkları
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
                },
            )

            # Birinci savunma katmanı: kendi ekstra init script'lerimiz.
            # navigator.webdriver, chrome runtime, plugins, languages, vb.
            self.context.add_init_script(
                """
                // navigator.webdriver gizle
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // Chrome runtime objesi (headless'ta eksik olur)
                window.chrome = window.chrome || { runtime: {}, loadTimes: function(){}, csi: function(){} };
                // Plugins (gerçek tarayıcıda boş değildir)
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'PDF Viewer', filename: 'internal-pdf-viewer'},
                        {name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer'},
                        {name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer'},
                        {name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer'},
                        {name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer'}
                    ]
                });
                // Languages
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'tr']});
                // Permissions API fix
                const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
                if (originalQuery) {
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications'
                            ? Promise.resolve({ state: Notification.permission })
                            : originalQuery(parameters)
                    );
                }
                // WebGL vendor / renderer
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.apply(this, arguments);
                };
                """
            )

            self.page = self.context.new_page()

            # İkinci savunma katmanı: playwright-stealth tüm evasyonları
            # otomatik olarak ekler (50+ fingerprint patch'i — chrome.app,
            # chrome.csi, iframe.contentWindow, broken-image, vb.).
            if STEALTH_AVAILABLE:
                try:
                    Stealth().apply_stealth_sync(self.context)
                    p_info("playwright-stealth uygulandı (context-level).")
                except Exception as stealth_err:
                    p_warn(f"playwright-stealth uygulanamadı: {stealth_err}")
            else:
                p_warn(
                    "playwright-stealth devre dışı (kütüphane yok); "
                    "yalnızca kendi init script'lerimiz aktif."
                )

            p_info("Playwright browser initialized successfully.")
        except Exception as e:
            p_error(f"Failed to initialize Playwright browser: {e}")
            raise e

    def _human_type(self, selector: str, text: str):
        """
        Arama kutusuna metni harf harf, her tuşa rastgele gecikme vererek
        yazar. Sabit gecikme → bot imzası, rastgele insansı.
        """
        # Önce locator'ı al ve odakla; doğrudan locator.type(...) kullan.
        locator = self.page.locator(selector).first
        try:
            locator.click(timeout=3000)
        except Exception:
            pass
        for char in text:
            # Her karakter için 80-180ms; cümle aralarında daha uzun pause
            delay_ms = random.randint(80, 180)
            locator.type(char, delay=delay_ms)
            # Rastgele "düşünme molası" — insan yazımında ~%10 oranında
            if random.random() < 0.08:
                human_delay(0.25, 0.75)

    def _scroll_like_human(self):
        """Scrolls the page in a human-like manner."""
        scroll_amount = random.randint(200, 500)
        self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        human_delay(0.5, 1.5)

    def _accept_cookies(self):
        """
        Google'ın çerez onay diyalogunu kapatmaya çalışır.
        - Hem ana frame'de hem de Google'ın consent.google.com iframe'inde arar.
        - Birden çok dil/varyant destekler (TR, EN, "Reject all", "Sadece gerekli").
        - Her aday için kısa timeout, try-except ile sessiz başarısızlık.
        """
        accept_selectors = [
            # Common Google "Accept" button IDs / generic selectors
            "#L2AGLb",                          # Klasik "Accept all" / "Hepsini Kabul"
            "button#L2AGLb",
            "button[aria-label*='Accept all']",
            "button[aria-label*='Tümünü kabul']",
            "button[aria-label*='Kabul et']",
            # Text-based (case-insensitive)
            "button:has-text('Accept all')",
            "button:has-text('Tümünü kabul et')",
            "button:has-text('Tümünü Kabul Et')",
            "button:has-text('Kabul et')",
            "button:has-text('Kabul Et')",
            "button:has-text('Accept')",
            "button:has-text('I agree')",
            "button:has-text('Agree')",
            # Reject-all also dismisses the banner; kabul edilir alternatif
            "button:has-text('Reject all')",
            "button:has-text('Tümünü reddet')",
            "button:has-text('Sadece gerekli')",
            # role=button fallback'leri
            "[role='button']:has-text('Accept all')",
            "[role='button']:has-text('Tümünü kabul et')",
            "form[action*='consent'] button",
        ]

        def _try_click_in(frame):
            for selector in accept_selectors:
                try:
                    locator = frame.locator(selector).first
                    if locator.count() > 0 and locator.is_visible(timeout=1000):
                        locator.click(timeout=2500)
                        p_log(f"Cookie consent dismissed via selector: {selector}")
                        human_delay(0.4, 0.9)
                        return True
                except Exception:
                    continue
            return False

        try:
            human_delay(1, 2)
            # 1) Ana frame
            if _try_click_in(self.page):
                return True
            # 2) consent.google.com iframe'i (eski akış için)
            for f in self.page.frames:
                try:
                    if "consent" in (f.url or "") or "consent" in (f.name or ""):
                        if _try_click_in(f):
                            return True
                except Exception:
                    continue
        except Exception as e:
            p_log(f"Çerez diyalogu işlenirken sessiz hata: {e}")
        return False

    def _debug_screenshot(self, tag: str = "google_0_results"):
        """0-sonuç / hata teşhisi için ekran görüntüsü ve HTML dump alır."""
        try:
            import os, datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            png_path = f"debug_{tag}_{ts}.png"
            html_path = f"debug_{tag}_{ts}.html"
            self.page.screenshot(path=png_path, full_page=True)
            try:
                html = self.page.content()
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception:
                pass
            p_warn(
                f"DEBUG: Ekran görüntüsü '{png_path}' ve sayfa HTML'i "
                f"'{html_path}' olarak kaydedildi. Çerez/captcha kontrolü için inceleyin."
            )
        except Exception as e:
            p_warn(f"Debug screenshot alınamadı: {e}")

    def search(self, query: str, num_results: int = 10) -> list[str]:
        """
        Performs an organic Google search and returns a list of result URLs.
        """
        if not self.page:
            self.init_browser()

        p_info(f"Step 2: Navigating to Google...")
        results = set()

        try:
            # `networkidle` Google'ın sürekli ping/telemetry trafiği yüzünden bazen
            # asla tetiklenmiyor; daha tolerant bir bekleme stratejisi.
            try:
                self.page.goto(
                    "https://www.google.com",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
            except Exception as nav_err:
                p_warn(f"Google goto sırasında zaman aşımı/uyarı: {nav_err}")
            human_delay(1.5, 3)

            self._accept_cookies()
            human_delay(0.5, 1.5)

            # İnsansı "sayfayı okuyup düşünme" molası: 1-3 sn.
            # Anti-bot sistemleri, "goto" → "type" arası mikro saniye düzeyinde
            # interaction'ı şüpheli görüyor; bilinçli rastgele gecikme bunu maskeler.
            pre_search_pause = random.uniform(1.0, 3.0)
            p_log(f"Pre-search insansı bekleme: {pre_search_pause:.2f}s")
            import time
            time.sleep(pre_search_pause)

            # Küçük bir fare hareketi de "gerçek kullanıcı" sinyali için ekstra puan
            try:
                self.page.mouse.move(
                    random.randint(100, 800),
                    random.randint(100, 500),
                    steps=random.randint(5, 15),
                )
            except Exception:
                pass

            p_info(f"Step 3: Typing search query: '{query}'")

            # Find and click search box
            search_selectors = ["textarea[name='q']", "input[name='q']"]
            search_box = None
            for sel in search_selectors:
                if self.page.locator(sel).count() > 0:
                    search_box = sel
                    break

            if not search_box:
                p_error("Could not find search box on Google.")
                return list(results)

            # Doğrudan click(selector) yerine locator-tabanlı; _human_type da
            # locator.type kullanıyor. Tutarlı API.
            try:
                self.page.locator(search_box).first.click(timeout=4000)
            except Exception:
                pass
            human_delay(0.3, 0.8)

            # Harf harf, rastgele gecikmeli insansı yazım
            self._human_type(search_box, query)
            human_delay(0.5, 1.5)

            # Press Enter
            self.page.press(search_box, "Enter")
            p_info("Step 4: Waiting for search results...")
            # `networkidle` yerine: arama sonuç container'ından biri görünür
            # olana kadar bekle. Google bazen sonsuz analytics ping'i yüzünden
            # idle olmuyor; bu yaklaşım daha güvenilir.
            result_container_selectors = [
                "#search",                       # Klasik ana arama kapsayıcısı
                "#rso",                          # Search results list container
                "div[data-async-context]",       # Async batched results
                "div[role='main']",              # Fallback ana içerik
            ]
            container_seen = False
            for sel in result_container_selectors:
                try:
                    self.page.wait_for_selector(sel, timeout=8000, state="attached")
                    container_seen = True
                    p_log(f"Arama sonuç kapsayıcısı yüklendi: {sel}")
                    break
                except Exception:
                    continue
            if not container_seen:
                p_warn(
                    "Arama sonuç kapsayıcısı (#search/#rso) görünür olmadı — "
                    "Google captcha veya farklı bir layout sunmuş olabilir."
                )
                # Captcha veya consent re-prompt için son bir çerez denemesi:
                self._accept_cookies()
            human_delay(2, 4)

            p_info("Step 5: Extracting URLs from search results...")

            page_count = 0
            max_pages = (num_results // 10) + 2

            while len(results) < num_results and page_count < max_pages:
                page_count += 1
                p_log(f"Processing page {page_count}...")

                # Scroll like human
                for _ in range(random.randint(2, 4)):
                    self._scroll_like_human()

                human_delay(1, 2)

                # Extract URLs using multiple robust methods
                # Use Playwright to extract links with JavaScript (most reliable)
                extracted_urls = self.page.evaluate(
                    """
                    () => {
                        const urls = new Set();
                        
                        // Method 1: Links with jsname attribute (Google's internal naming)
                        document.querySelectorAll('a[jsname]').forEach(a => {
                            const href = a.getAttribute('href');
                            if (href && href.startsWith('http') && !href.includes('google.com') && !href.includes('youtube.com')) {
                                urls.add(href);
                            }
                        });
                        
                        // Method 2: Links inside h3 elements (search result titles)
                        document.querySelectorAll('h3').forEach(h3 => {
                            const parent = h3.closest('a');
                            if (parent && parent.href) {
                                const href = parent.href;
                                if (href.startsWith('http') && !href.includes('google.com') && !href.includes('youtube.com')) {
                                    urls.add(href);
                                }
                            }
                        });
                        
                        // Method 3: Links with cite elements nearby (showing URL)
                        document.querySelectorAll('cite').forEach(cite => {
                            const container = cite.closest('div');
                            if (container) {
                                const link = container.querySelector('a[href^="http"]') || container.parentElement?.querySelector('a[href^="http"]');
                                if (link && link.href && !link.href.includes('google.com')) {
                                    urls.add(link.href);
                                }
                            }
                        });
                        
                        // Method 4: All links that look like search results
                        document.querySelectorAll('a[href^="http"]').forEach(a => {
                            const href = a.href;
                            // Filter out Google internal links and common non-result links
                            if (href && 
                                !href.includes('google.com') && 
                                !href.includes('youtube.com') &&
                                !href.includes('accounts.google') &&
                                !href.includes('support.google') &&
                                !href.includes('policies.google') &&
                                !href.includes('maps.google') &&
                                !href.includes('translate.google') &&
                                !href.startsWith('https://webcache.') &&
                                !href.includes('/search?') &&
                                !href.includes('javascript:')) {
                                // Check if this looks like a real result (has a parent with certain depth)
                                let parent = a.parentElement;
                                let depth = 0;
                                while (parent && depth < 10) {
                                    if (parent.tagName === 'DIV') depth++;
                                    parent = parent.parentElement;
                                }
                                if (depth >= 3) {
                                    urls.add(href);
                                }
                            }
                        });
                        
                        return Array.from(urls);
                    }
                """
                )

                for url in extracted_urls:
                    if url not in results:
                        results.add(url)

                p_log(f"Collected {len(results)}/{num_results} URLs so far...")

                if len(results) >= num_results:
                    break

                # Next page
                try:
                    next_btn = self.page.locator("#pnnext")
                    if next_btn.count() > 0:
                        next_btn.click()
                        p_log("Navigating to next page...")
                        self.page.wait_for_load_state("networkidle")
                        human_delay(2, 4)
                    else:
                        p_warn("No more pages available.")
                        break
                except:
                    break

        except Exception as e:
            p_error(f"Error during search: {e}")
            # Beklenmedik hatada da bir screenshot al — captcha / consent /
            # network issue olabilir; teşhis için kritik.
            try:
                self._debug_screenshot("google_search_exception")
            except Exception:
                pass
        finally:
            # Kapanmadan ÖNCE: hâlâ 0 sonuç varsa debug snapshot al.
            # Bu kullanıcının istediği "ekran görüntüsü ile teşhis" davranışı.
            try:
                if len(results) == 0 and self.page is not None:
                    self._debug_screenshot("google_0_results")
            except Exception:
                pass
            self.close()

        p_info(f"Step 6: Search completed. Total unique URLs found: {len(results)}")
        return list(results)[:num_results]

    def close(self):
        """Closes the browser and cleans up resources."""
        p_info("Closing Playwright browser...")
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
