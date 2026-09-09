"""
Script de keepalive pour Streamlit Community Cloud.

Ouvre l'app dans un vrai navigateur headless (Chromium), et clique sur le
bouton "Yes, get this app back up!" s'il apparaît (= l'app était en veille).

Un simple GET HTTP ne suffit pas : Streamlit renvoie une page statique 200
sans relancer le vrai processus Python. Il faut un navigateur qui charge le
JS et ouvre la connexion WebSocket, d'où l'usage de Playwright.

Usage :
    python keepalive.py
"""

import asyncio
import sys
from playwright.async_api import async_playwright

# --- À adapter ---
APP_URLS = [
    "https://jobagent-ai-taxhx9jqu3drmxss6muhkg.streamlit.app/",
    # Ajoute ici d'autres URLs si tu as plusieurs apps à garder éveillées
]
WAKE_BUTTON_TEXT = "Yes, get this app back up!"
LOAD_TIMEOUT_MS = 60_000
POST_CLICK_WAIT_MS = 30_000


async def wake_app(browser, url: str) -> None:
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
        # Laisse le temps au front Streamlit de détecter l'état "sleeping"
        await page.wait_for_timeout(5000)

        wake_button = page.get_by_role("button", name=WAKE_BUTTON_TEXT)
        if await wake_button.count() > 0:
            print(f"[SLEEPING] {url} -> clic sur le bouton de réveil")
            await wake_button.click()
            # Attend que l'app redémarre réellement avant de fermer la page
            await page.wait_for_timeout(POST_CLICK_WAIT_MS)
            print(f"[WOKEN UP] {url}")
        else:
            print(f"[OK] {url} était déjà éveillée")
    except Exception as exc:
        print(f"[ERREUR] {url} -> {exc}", file=sys.stderr)
    finally:
        await page.close()


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            for url in APP_URLS:
                await wake_app(browser, url)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
