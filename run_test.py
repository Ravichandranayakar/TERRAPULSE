from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        errors = []
        page.on("pageerror", lambda err: errors.append(f"PageError: {err}"))
        page.on("console", lambda msg: errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ['error', 'warning'] else None)
        
        print("Navigating...")
        page.goto("http://localhost:5173/")
        
        # Switch to Nepal mode if possible
        time.sleep(5)
        print("Clicking NEPAL LIVE...")
        # find the button containing "NEPAL (LIVE)"
        nepal_btn = page.locator("button:has-text('NEPAL (LIVE)')")
        if nepal_btn.count() > 0:
            nepal_btn.first.click()
            
        time.sleep(8)
        
        print("Clicking a cell...")
        cells = page.locator("svg g.cursor-pointer")
        print("Found", cells.count(), "cells")
        if cells.count() > 0:
            cells.first.click()
            time.sleep(3)
        else:
            print("No cells found!")
            
        print("Errors captured:")
        for err in errors:
            print(err)
            
        browser.close()

run()
