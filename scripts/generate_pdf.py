#!/usr/bin/env python3
"""
Generate a publication-grade Persian PDF for the Kalam Whitepaper using Headless Chrome.
"""

import base64
import os
import subprocess
import markdown

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_PATH = os.path.join(WORKSPACE, "WHITEPAPER.md")
LOGO_PATH = os.path.join(WORKSPACE, "kalam_logo.jpg")
HTML_OUT = os.path.join(WORKSPACE, "whitepaper_render.html")
PDF_OUT = os.path.join(WORKSPACE, "WHITEPAPER_KALAM.pdf")

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def get_logo_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/jpeg;base64,{data}"
    return ""

def build_html():
    raw_md = read_file(MD_PATH)
    logo_b64 = get_logo_base64(LOGO_PATH)
    
    # Pre-process math markers so KaTeX or CSS formats them nicely
    # Convert mermaid blocks to styled pre/code blocks
    md_content = raw_md
    
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc"]
    )
    
    # Replace image markdown tag if present with the base64 logo
    if logo_b64:
        html_body = html_body.replace(
            '<p><img alt="لوگوی رسمی پروژه کلم"',
            f'<p style="text-align:center;"><img style="max-width:280px; border-radius:24px; box-shadow:0 12px 30px rgba(0,0,0,0.12);" src="{logo_b64}" alt="لوگوی رسمی پروژه کلم"'
        )
    
    full_html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>وایت‌پیپر رسمی پروژه کَلَم (Kalam)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{
        delimiters: [
            {{left: '$$', right: '$$', display: true}},
            {{left: '$', right: '$', display: false}}
        ]
    }});"></script>

<style>
@page {{
    size: A4;
    margin: 22mm 18mm 22mm 18mm;
    @bottom-center {{
        content: "پروژه کَلَم — دستیار هوشمند خرید حضوری تهران | صفحه " counter(page);
        font-family: 'Vazirmatn', sans-serif;
        font-size: 8pt;
        color: #94A3B8;
    }}
}}

*, *::before, *::after {{
    box-sizing: border-box;
}}

body {{
    font-family: 'Vazirmatn', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.85;
    color: #1E293B;
    background-color: #FFFFFF;
    margin: 0;
    padding: 0;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
}}

/* Cover Page */
.cover-page {{
    page-break-after: always;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 90vh;
    text-align: center;
    padding: 40px 20px;
}}

.cover-logo {{
    width: 170px;
    height: 170px;
    border-radius: 36px;
    box-shadow: 0 20px 45px rgba(16, 185, 129, 0.22);
    margin-bottom: 28px;
    object-fit: contain;
}}

.cover-title {{
    font-size: 34pt;
    font-weight: 900;
    color: #0F172A;
    margin: 0 0 10px 0;
    letter-spacing: -0.5px;
}}

.cover-title span.kalam-accent {{
    color: #10B981;
}}

.cover-title span.torob-accent {{
    color: #D32F2F;
}}

.cover-subtitle {{
    font-size: 14pt;
    font-weight: 500;
    color: #475569;
    max-width: 600px;
    margin: 0 auto 30px auto;
    line-height: 1.6;
}}

.cover-badge-row {{
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-bottom: 45px;
}}

.cover-badge {{
    background: #F1F5F9;
    color: #334155;
    padding: 6px 16px;
    border-radius: 999px;
    font-size: 9pt;
    font-weight: 600;
    border: 1px solid #E2E8F0;
}}

.cover-badge.highlight {{
    background: #ECFDF5;
    color: #065F46;
    border-color: #A7F3D0;
}}

.cover-meta {{
    margin-top: 40px;
    padding-top: 25px;
    border-top: 2px solid #F1F5F9;
    width: 100%;
    max-width: 450px;
    font-size: 9.5pt;
    color: #64748B;
    line-height: 1.8;
}}

.cover-meta strong {{
    color: #1E293B;
}}

/* Typography & Headings */
h1, h2, h3, h4, h5, h6 {{
    font-family: 'Vazirmatn', sans-serif;
    color: #0F172A;
    font-weight: 700;
    page-break-after: avoid;
    break-after: avoid;
}}

h1 {{
    font-size: 20pt;
    font-weight: 800;
    color: #111827;
    border-bottom: 2.5px solid #10B981;
    padding-bottom: 8px;
    margin-top: 36px;
    margin-bottom: 18px;
}}

h2 {{
    font-size: 15pt;
    color: #047857;
    margin-top: 28px;
    margin-bottom: 14px;
    border-right: 4px solid #10B981;
    padding-right: 12px;
}}

h3 {{
    font-size: 12pt;
    color: #1E293B;
    margin-top: 22px;
    margin-bottom: 10px;
}}

p {{
    margin: 0 0 14px 0;
    text-align: justify;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
    break-inside: avoid;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}

th, td {{
    padding: 10px 14px;
    text-align: right;
    border: 1px solid #E2E8F0;
}}

th {{
    background-color: #0F172A;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 9pt;
}}

tr:nth-child(even) {{
    background-color: #F8FAFC;
}}

tr:hover {{
    background-color: #F1F5F9;
}}

/* Code & Pre */
pre {{
    background-color: #0F172A;
    color: #F8FAFC;
    padding: 14px 18px;
    border-radius: 10px;
    overflow-x: auto;
    font-family: 'Fira Code', monospace;
    font-size: 8.5pt;
    line-height: 1.6;
    direction: ltr;
    text-align: left;
    margin: 18px 0;
    page-break-inside: avoid;
    break-inside: avoid;
    border: 1px solid #334155;
}}

code {{
    font-family: 'Fira Code', monospace;
    font-size: 8.5pt;
    background-color: #F1F5F9;
    color: #0F172A;
    padding: 2px 6px;
    border-radius: 5px;
    direction: ltr;
    display: inline-block;
}}

pre code {{
    background-color: transparent;
    color: inherit;
    padding: 0;
}}

/* Blockquotes & Callouts */
blockquote {{
    margin: 18px 0;
    padding: 14px 20px;
    background-color: #ECFDF5;
    border-right: 5px solid #10B981;
    border-radius: 0 10px 10px 0;
    color: #065F46;
    font-weight: 500;
    page-break-inside: avoid;
}}

blockquote p {{
    margin: 0;
}}

/* Lists */
ul, ol {{
    margin: 0 0 16px 0;
    padding-right: 22px;
}}

li {{
    margin-bottom: 6px;
}}

hr {{
    border: 0;
    height: 1px;
    background: #E2E8F0;
    margin: 28px 0;
}}

/* Page break utility */
.page-break {{
    page-break-after: always;
    break-after: page;
}}
</style>
</head>
<body>

<div class="cover-page">
    <img src="{logo_b64}" class="cover-logo" alt="لوگوی رسمی کَلَم">
    <div class="cover-title">وایت‌پیپر رسمی پروژه <span class="kalam-accent">کَلَم</span></div>
    <div class="cover-subtitle">پلتفرم هوش مصنوعی و دستیار خرید حضوری از بازارها، پاساژها و مراکز خرید تهران</div>
    
    <div class="cover-badge-row">
        <span class="cover-badge highlight">هکاتون ترب ۲۰۲۶ (Torob AI Hackathon)</span>
        <span class="cover-badge">نسخه ۱.۰ تجاری</span>
        <span class="cover-badge">معماری سیستم و وایت‌پیپر رسمی</span>
    </div>
    
    <div class="cover-meta">
        <div><strong>طراحی و مهندسی:</strong> تیم سیستم‌های هوشمند کَلَم</div>
        <div><strong>زیرساخت فنی:</strong> SQLite FTS5 + FastAPI + Gemini 2.0 Flash</div>
        <div><strong>پوشش داده:</strong> ۶,۴۷۶ فروشگاه | ۲۲۵,۹۰۳ کالا | ۳۳۱,۵۰۶ آفر ترب</div>
        <div><strong>تاریخ انتشار:</strong> آبان ۱۴۰۵ / اکتبر ۲۰۲۶</div>
    </div>
</div>

<div class="content-body">
{html_body}
</div>

</body>
</html>
"""
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"HTML generated at {HTML_OUT}")

def render_pdf():
    chrome_cmd = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-file-access-from-files",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={PDF_OUT}",
        HTML_OUT
    ]
    print("Running Chrome headless to render PDF...")
    result = subprocess.run(chrome_cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(PDF_OUT):
        size_kb = os.path.getsize(PDF_OUT) / 1024
        print(f"SUCCESS: PDF created at {PDF_OUT} ({size_kb:.1f} KB)")
    else:
        print(f"FAILED: Chrome exited with code {result.returncode}")
        print("Stderr:", result.stderr)

if __name__ == "__main__":
    build_html()
    render_pdf()
