
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

SCREENSHOTS_DIR = Path("C:/Users/USUÁRIO/Desktop/Projetos/vigilia_portaria/dom_screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)

report = {
    "steps": [],
    "errors": [],
    "selectors": {},
    "dom_snapshots": {}
}

def log(msg):
    print(f"[DOM-MAP] {msg}", flush=True)

def take_screenshot(page, name, description=""):
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    log(f"Screenshot saved: {name}.png - {description}")
    return str(path)

def get_outer_html(page, selector, label=""):
    try:
        el = page.query_selector(selector)
        if el:
            html = el.evaluate("el => el.outerHTML")
            log(f"Got HTML for '{label}': {html[:300]}")
            return html
        else:
            log(f"Element not found: {selector}")
            return None
    except Exception as e:
        log(f"Error getting HTML for {selector}: {e}")
        return None

def find_element_by_text(page, text, tag="*"):
    try:
        elements = page.query_selector_all(f"{tag}:has-text('{text}')")
        found = []
        for el in elements:
            tag_name = el.evaluate("el => el.tagName")
            classes = el.evaluate("el => el.className")
            id_ = el.evaluate("el => el.id")
            text_content = el.inner_text()[:100] if el.inner_text() else ""
            found.append({
                "tag": tag_name,
                "classes": classes,
                "id": id_,
                "text": text_content
            })
        return found
    except Exception as e:
        log(f"Error finding elements by text '{text}': {e}")
        return []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    page = context.new_page()

    # ─── STEP 1: Navigate to portal ───────────────────────────────────────────
    log("STEP 1: Navigating to portal...")
    try:
        page.goto("https://portal.doe.sea.sc.gov.br/v2.43.01/#/portal", wait_until="networkidle", timeout=30000)
    except Exception as e:
        log(f"Navigation warning: {e}")

    log("Waiting 8s for Angular to initialize...")
    time.sleep(8)

    take_screenshot(page, "01_initial_page", "Initial portal page after Angular init")
    
    # Get page title and main structure
    title = page.title()
    log(f"Page title: {title}")
    
    # Capture main app structure
    app_html = get_outer_html(page, "app-root", "app-root")
    nav_html = get_outer_html(page, "nav", "navigation")
    
    # Find all visible links/buttons
    all_links = page.evaluate("""
        () => Array.from(document.querySelectorAll('a, button')).map(el => ({
            tag: el.tagName,
            text: el.innerText.trim().substring(0, 80),
            href: el.href || '',
            id: el.id,
            class: el.className.substring(0, 100),
            routerlink: el.getAttribute('routerlink') || el.getAttribute('ng-reflect-router-link') || ''
        })).filter(el => el.text.length > 0)
    """)
    log(f"All visible links/buttons on initial page: {json.dumps(all_links, ensure_ascii=False)[:3000]}")
    report["steps"].append({
        "step": 1,
        "description": "Initial page loaded",
        "title": title,
        "links_found": all_links
    })

    # ─── STEP 2: Find and click 'Buscar Edições' ──────────────────────────────
    log("STEP 2: Finding 'Buscar Edições' link...")
    
    buscar_found = False
    
    # Try multiple strategies
    strategies = [
        lambda: page.click("a:has-text('Buscar Edições')", timeout=5000),
        lambda: page.click("a:has-text('Buscar Edicoes')", timeout=5000),
        lambda: page.click("button:has-text('Buscar Edições')", timeout=5000),
        lambda: page.click("[routerlink*='buscar']", timeout=5000),
        lambda: page.click("[href*='buscar']", timeout=5000),
        lambda: page.click("text=Buscar Edições", timeout=5000),
    ]
    
    for i, strategy in enumerate(strategies):
        try:
            strategy()
            log(f"Clicked 'Buscar Edições' using strategy {i+1}")
            buscar_found = True
            break
        except Exception as e:
            log(f"Strategy {i+1} failed: {e}")
    
    if not buscar_found:
        log("All direct strategies failed. Inspecting all anchor tags...")
        anchors = page.evaluate("""
            () => Array.from(document.querySelectorAll('a')).map(el => ({
                text: el.innerText.trim(),
                href: el.href,
                routerlink: el.getAttribute('routerlink') || '',
                'ng-reflect': el.getAttribute('ng-reflect-router-link') || '',
                class: el.className
            }))
        """)
        log(f"All anchors: {json.dumps(anchors, ensure_ascii=False)}")
        
        # Try clicking by routerlink
        try:
            page.click("[ng-reflect-router-link*='edicao']", timeout=5000)
            buscar_found = True
            log("Clicked via ng-reflect-router-link")
        except:
            pass
        
        if not buscar_found:
            try:
                page.click("[ng-reflect-router-link*='busca']", timeout=5000)
                buscar_found = True
                log("Clicked via ng-reflect-router-link busca")
            except:
                pass

    time.sleep(5)
    take_screenshot(page, "02_after_buscar_click", "After clicking Buscar Edições")
    
    current_url = page.url
    log(f"Current URL after click: {current_url}")
    
    # Get all visible elements again
    all_links_2 = page.evaluate("""
        () => Array.from(document.querySelectorAll('a, button')).map(el => ({
            tag: el.tagName,
            text: el.innerText.trim().substring(0, 80),
            id: el.id,
            class: el.className.substring(0, 100),
        })).filter(el => el.text.length > 0)
    """)
    log(f"Links/buttons after navigation: {json.dumps(all_links_2, ensure_ascii=False)[:3000]}")

    # ─── STEP 3: Find and click filter button ─────────────────────────────────
    log("STEP 3: Finding filter button...")
    
    filter_found = False
    filter_strategies = [
        ("button .pi-filter", "PI filter icon parent"),
        (".pi-filter", "PI filter icon"),
        ("button:has-text('Filtros')", "Filtros text button"),
        ("button:has-text('Filtrar')", "Filtrar text button"),
        ("[class*='filter']", "Filter class"),
        ("button.p-button:has(.pi-filter)", "PrimeNG filter button"),
    ]
    
    for selector, desc in filter_strategies:
        try:
            page.click(selector, timeout=5000)
            log(f"Clicked filter using: {selector} ({desc})")
            filter_found = True
            report["selectors"]["filter_button"] = selector
            break
        except Exception as e:
            log(f"Filter strategy '{desc}' failed: {e}")
    
    if not filter_found:
        log("Trying to find filter button by inspecting all buttons...")
        buttons = page.evaluate("""
            () => Array.from(document.querySelectorAll('button')).map(el => ({
                text: el.innerText.trim(),
                title: el.title,
                id: el.id,
                class: el.className,
                ariaLabel: el.getAttribute('aria-label') || '',
                innerHTML: el.innerHTML.substring(0, 200)
            }))
        """)
        log(f"All buttons found: {json.dumps(buttons, ensure_ascii=False)[:5000]}")
    
    time.sleep(3)
    take_screenshot(page, "03_after_filter_click", "After clicking filter button")

    # ─── STEP 4: Inspect filter modal ─────────────────────────────────────────
    log("STEP 4: Inspecting filter modal/panel...")
    
    # Look for modal/dialog
    modal_selectors = [
        "p-dialog",
        ".p-dialog",
        "p-sidebar",
        ".p-sidebar",
        "[role='dialog']",
        ".modal",
        "p-overlaypanel",
    ]
    
    for sel in modal_selectors:
        el = page.query_selector(sel)
        if el:
            log(f"Found modal/panel: {sel}")
            html = el.evaluate("el => el.outerHTML")
            log(f"Modal HTML: {html[:2000]}")
            report["dom_snapshots"]["filter_modal"] = {"selector": sel, "html": html[:5000]}
            break
    
    # Find all input fields in the modal
    inputs = page.evaluate("""
        () => Array.from(document.querySelectorAll('input, p-dropdown, p-calendar, p-multiselect')).map(el => ({
            tag: el.tagName,
            type: el.type || '',
            placeholder: el.placeholder || '',
            id: el.id,
            class: el.className.substring(0, 150),
            name: el.name || '',
            ariaLabel: el.getAttribute('aria-label') || '',
            ngModel: el.getAttribute('ng-reflect-model') || '',
            labelEl: ''
        }))
    """)
    log(f"Input fields found: {json.dumps(inputs, ensure_ascii=False)}")
    report["dom_snapshots"]["inputs"] = inputs

    # Find placeholders specifically
    placeholders = page.evaluate("""
        () => {
            const result = [];
            // Check all inputs
            document.querySelectorAll('input').forEach(el => {
                if (el.placeholder) {
                    result.push({type: 'input', placeholder: el.placeholder, class: el.className.substring(0, 100)});
                }
            });
            // Check p-dropdown labels
            document.querySelectorAll('p-dropdown').forEach(el => {
                const label = el.querySelector('.p-dropdown-label');
                if (label) {
                    result.push({type: 'p-dropdown', label: label.innerText.trim(), class: el.className.substring(0, 100)});
                }
                const placeholder = el.getAttribute('placeholder');
                if (placeholder) {
                    result.push({type: 'p-dropdown-attr', placeholder, class: el.className.substring(0, 100)});
                }
            });
            // p-multiselect
            document.querySelectorAll('p-multiselect').forEach(el => {
                const label = el.querySelector('.p-multiselect-label');
                if (label) {
                    result.push({type: 'p-multiselect', label: label.innerText.trim(), class: el.className.substring(0, 100)});
                }
            });
            return result;
        }
    """)
    log(f"Placeholders/labels found: {json.dumps(placeholders, ensure_ascii=False)}")
    report["dom_snapshots"]["placeholders"] = placeholders

    # Find Aplicar button
    aplicar_elements = find_element_by_text(page, "Aplicar")
    log(f"'Aplicar' elements: {json.dumps(aplicar_elements, ensure_ascii=False)}")
    report["selectors"]["aplicar_elements"] = aplicar_elements

    # ─── STEP 5: Click category dropdown ──────────────────────────────────────
    log("STEP 5: Clicking category dropdown...")
    
    cat_strategies = [
        "p-dropdown[placeholder*='Categoria']",
        "p-dropdown[ng-reflect-placeholder*='Categoria']",
        "p-dropdown[ng-reflect-placeholder*='categoria']",
        ".p-dropdown:first-of-type",
    ]
    
    cat_clicked = False
    for sel in cat_strategies:
        try:
            page.click(sel, timeout=5000)
            log(f"Clicked category dropdown: {sel}")
            cat_clicked = True
            report["selectors"]["category_dropdown"] = sel
            break
        except Exception as e:
            log(f"Category dropdown strategy '{sel}' failed: {e}")
    
    if not cat_clicked:
        # Try clicking first dropdown
        try:
            dropdowns = page.query_selector_all("p-dropdown")
            log(f"Found {len(dropdowns)} p-dropdown elements")
            if dropdowns:
                dropdowns[0].click()
                cat_clicked = True
                log("Clicked first p-dropdown")
        except Exception as e:
            log(f"First dropdown click failed: {e}")
    
    time.sleep(2)
    
    # Get dropdown options
    dropdown_options = page.evaluate("""
        () => {
            const panel = document.querySelector('.p-dropdown-panel, p-dropdownpanel');
            if (!panel) return {found: false, options: []};
            const items = panel.querySelectorAll('.p-dropdown-item, li');
            return {
                found: true,
                options: Array.from(items).map(el => ({
                    text: el.innerText.trim(),
                    class: el.className,
                    value: el.getAttribute('data-value') || ''
                }))
            };
        }
    """)
    log(f"Category dropdown options: {json.dumps(dropdown_options, ensure_ascii=False)}")
    report["dom_snapshots"]["category_options"] = dropdown_options
    
    take_screenshot(page, "04_category_dropdown_open", "Category dropdown opened")

    # ─── STEP 6: Click Aplicar ─────────────────────────────────────────────────
    log("STEP 6: Clicking Aplicar button...")
    
    # Press Escape first to close dropdown if open
    page.keyboard.press("Escape")
    time.sleep(1)
    
    aplicar_strategies = [
        "button:has-text('Aplicar')",
        "button:has-text('Aplicar filtros')",
        ".p-button:has-text('Aplicar')",
        "[label='Aplicar']",
    ]
    
    aplicar_clicked = False
    for sel in aplicar_strategies:
        try:
            page.click(sel, timeout=5000)
            log(f"Clicked Aplicar: {sel}")
            aplicar_clicked = True
            report["selectors"]["aplicar_button"] = sel
            break
        except Exception as e:
            log(f"Aplicar strategy '{sel}' failed: {e}")
    
    time.sleep(5)
    take_screenshot(page, "05_after_aplicar", "After clicking Aplicar")

    # ─── STEP 7: Inspect result cards ─────────────────────────────────────────
    log("STEP 7: Inspecting result cards...")
    
    result_cards = page.evaluate("""
        () => {
            const results = [];
            // Try various card selectors
            const selectors = [
                '.card', 'p-card', '.result-card', '.result-item',
                '[class*="card"]', 'app-card', '.item'
            ];
            
            let cards = [];
            for (const sel of selectors) {
                cards = document.querySelectorAll(sel);
                if (cards.length > 0) {
                    results.push({selector: sel, count: cards.length});
                    // Get first card HTML
                    if (cards[0]) {
                        results.push({
                            firstCardHTML: cards[0].outerHTML.substring(0, 1000),
                            selector: sel
                        });
                    }
                    break;
                }
            }
            
            // Find 'Saiba mais' or 'Abrir' links
            const saibaMais = Array.from(document.querySelectorAll('*')).filter(
                el => el.innerText && (
                    el.innerText.trim() === 'Saiba mais' || 
                    el.innerText.trim() === 'Abrir' ||
                    el.innerText.trim().includes('Saiba') ||
                    el.innerText.trim().includes('Abrir')
                )
            ).slice(0, 5).map(el => ({
                tag: el.tagName,
                text: el.innerText.trim(),
                class: el.className.substring(0, 100),
                href: el.href || '',
                outerHTML: el.outerHTML.substring(0, 300)
            }));
            
            return {cardSelectors: results, saibaMaisLinks: saibaMais};
        }
    """)
    log(f"Result cards structure: {json.dumps(result_cards, ensure_ascii=False)[:5000]}")
    report["dom_snapshots"]["result_cards"] = result_cards

    # Get full page structure for result area
    main_content = page.evaluate("""
        () => {
            const main = document.querySelector('main, [role="main"], app-busca, app-search, .content-area, router-outlet + *');
            return main ? main.outerHTML.substring(0, 5000) : 'Not found';
        }
    """)
    log(f"Main content area HTML: {main_content[:2000]}")

    # Final screenshot
    take_screenshot(page, "06_final_results", "Final results page")
    
    # Get full DOM snapshot of visible area
    full_body_structure = page.evaluate("""
        () => {
            function getStructure(el, depth=0) {
                if (depth > 4) return '';
                const tag = el.tagName ? el.tagName.toLowerCase() : '';
                const id = el.id ? `#${el.id}` : '';
                const cls = el.className && typeof el.className === 'string' ? 
                    '.' + el.className.trim().replace(/\s+/g, '.').substring(0, 50) : '';
                const text = el.childNodes.length === 1 && el.childNodes[0].nodeType === 3 ? 
                    el.innerText.trim().substring(0, 30) : '';
                let str = `${' '.repeat(depth * 2)}<${tag}${id}${cls}>${text ? ' "' + text + '"' : ''}\n`;
                for (const child of el.children) {
                    str += getStructure(child, depth + 1);
                }
                return str;
            }
            return getStructure(document.body).substring(0, 8000);
        }
    """)
    log(f"Full body structure:\n{full_body_structure}")
    report["dom_snapshots"]["body_structure"] = full_body_structure

    browser.close()

# Save report
report_path = Path("C:/Users/USUÁRIO/Desktop/Projetos/vigilia_portaria/dom_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

log(f"Report saved to: {report_path}")
log("DOM mapping complete!")
