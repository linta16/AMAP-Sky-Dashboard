import os, json, glob, re
import pandas as pd
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
now = datetime.now(IST)
stamp = now.strftime('%d-%b-%y %H:%M')

# ── Read Defects ──────────────────────────────────────────────────────────────
defect_files = sorted(glob.glob('data/defects/*.csv') + glob.glob('data/defects/*.CSV'))
defects = []
if defect_files:
    latest = defect_files[-1]
    print(f"Loading defects from: {latest}")
    df = pd.read_csv(latest, encoding='utf-8-sig')
    df.columns = [c.strip().lower() for c in df.columns]
    defects = df.where(pd.notna(df), None).to_dict(orient='records')
    print(f"Loaded {len(defects)} defect rows")

# ── Read QA files ─────────────────────────────────────────────────────────────
qa_files = sorted(
    glob.glob('data/qa/*.csv') + glob.glob('data/qa/*.CSV') +
    glob.glob('data/qa/*.xlsx') + glob.glob('data/qa/*.XLSX')
)
qa_rows = []
for f in qa_files:
    print(f"Loading QA from: {f}")
    try:
        if f.lower().endswith('.csv'):
            df = pd.read_csv(f, encoding='utf-8-sig')
        else:
            df = pd.read_excel(f)
        df.columns = [c.strip().lower() for c in df.columns]
        rows = df.where(pd.notna(df), None).to_dict(orient='records')
        qa_rows.extend(rows)
        print(f"  → {len(rows)} rows")
    except Exception as e:
        print(f"  ⚠ Could not read {f}: {e}")

print(f"Total QA rows: {len(qa_rows)}")

# ── Read current index.html ───────────────────────────────────────────────────
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# ── Bake defects data ─────────────────────────────────────────────────────────
d_json = json.dumps(defects)
html = re.sub(r'var D=\[[\s\S]*?\];', f'var D={d_json};', html)

# ── Bake QA data ──────────────────────────────────────────────────────────────
qa_json = json.dumps(qa_rows)
qa_ts_json = json.dumps(f'Auto-refreshed: {stamp} · {len(qa_rows)} QA records')

if 'var _bakedQA=' in html:
    html = re.sub(r'var _bakedQA=\[[\s\S]*?\];', f'var _bakedQA={qa_json};', html)
    html = re.sub(r'var _bakedQAts=.*?;', f'var _bakedQAts={qa_ts_json};', html)
else:
    # Insert before closing script tag
    insert = f'\nvar _bakedQA={qa_json};\nvar _bakedQAts={qa_ts_json};\n'
    html = html.replace('</script>', insert + '</script>', 1)

# ── Update version stamp ──────────────────────────────────────────────────────
ver = now.strftime('v%Y.%m.%d.%H:%M')
html = re.sub(r'v2026\.\d{2}\.\d{2}\.\d{2}[:\-]\d{2}', ver, html)

# ── Write back ────────────────────────────────────────────────────────────────
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ Dashboard baked successfully — {len(defects)} defects, {len(qa_rows)} QA rows, stamp: {ver}")
