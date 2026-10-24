"""Real Chromium smoke tests. Uses a temporary database and fictional data only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'browser-artifacts'
ARTIFACTS.mkdir(exist_ok=True)

with tempfile.TemporaryDirectory() as temporary, (ARTIFACTS / 'server.log').open('w') as log:
    environment = {**os.environ, 'APPLYFLOW_DB': str(Path(temporary) / 'browser.db')}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '8123'],
                               cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    try:
        for attempt in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1:8123/api/health', timeout=1).close()
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError('Server failed; see browser-artifacts/server.log')
                time.sleep(.1)
        else:
            raise RuntimeError('Server did not become ready')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:8123')
            expect(page.locator('#total')).to_have_text('0')
            page.get_by_role('button', name='New application').focus()
            page.keyboard.press('Enter')
            expect(page.get_by_label('Company', exact=True)).to_be_focused()
            page.get_by_label('Company', exact=True).fill('Browser Example Labs')
            page.get_by_label('Role', exact=True).fill('Software Engineering Intern')
            page.get_by_label('Location', exact=True).fill('London')
            page.get_by_label('Notes', exact=True).fill('<img src=x onerror=alert(1)>')
            page.locator('#save-application').click()
            expect(page.locator('#total')).to_have_text('1')
            page.get_by_role('button', name='Edit Browser Example Labs: Software Engineering Intern', exact=True).click()
            page.get_by_label('Status', exact=True).select_option('Interview')
            page.locator('#save-application').click()
            expect(page.locator('#in-progress')).to_have_text('1')
            page.reload()
            expect(page.locator('#rows')).to_contain_text('Browser Example Labs')
            page.get_by_role('button', name='Import CSV', exact=True).click()
            page.locator('#csv-file').set_input_files(ROOT / 'examples/applications.csv')
            page.locator('#import-submit').click()
            expect(page.locator('#total')).to_have_text('4')
            page.get_by_label('Search applications').fill('Browser Example Labs')
            expect(page.locator('#page-label')).to_have_text('1–1 of 1 applications')
            with page.expect_download() as info:
                page.get_by_role('link', name='Export CSV').click()
            assert info.value.suggested_filename.endswith('.csv')
            page.get_by_label('Search applications').fill('')
            expect(page.locator('#page-label')).to_have_text('1–4 of 4 applications')
            page.screenshot(path=str(ARTIFACTS / 'desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Page overflows mobile viewport'
            page.screenshot(path=str(ARTIFACTS / 'mobile.png'), full_page=True)
            page.get_by_role('button', name='New application').click()
            page.keyboard.press('Escape')
            expect(page.locator('#editor')).not_to_be_visible()
            page.on('dialog', lambda dialog: dialog.accept())
            page.get_by_role('button', name='Remove Browser Example Labs: Software Engineering Intern', exact=True).click()
            expect(page.locator('#total')).to_have_text('3')
            assert not errors, errors
            browser.close()
        print('PASS: Chromium CRUD, persistence, CSV import/export, search, keyboard dialog and 1440/390px layout smoke checks')
    finally:
        process.terminate()
        process.wait(timeout=10)
