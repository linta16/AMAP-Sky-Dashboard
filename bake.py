import os, json, glob, re
import pandas as pd
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
now = datetime.now(IST)
stamp = now.strftime('%d-%b-%y %H:%M')

# Read Defects
defect_files = sorted(glob.glob('data/defects/*.csv') + glob.glob('data/defects/*.CSV'))
defects = []
if defect_files:
    latest = defect_files[-1]
    print(f"Loading defects from: {latest}")
    df = pd.read_csv(latest, encoding='utf-8-sig')
    df.columns = [c.strip().lower() for c in df.columns]
    defects = df.where(pd.notna(df), None).to_dict(orient='records')
    print(f"Loaded {len(defects)} defect rows")

# Read QA files
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
        print(f"  -> {len(rows)} rows")
    except Exception as e:
        print(f"  WARNING: Could not read {f}: {e}")

print(f"Total QA rows: {len(qa_rows)}")

# Read index.html
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f"index.html size before bake: {len(html)} bytes")

# Bake defects - replace var D=anything;
d_json = json.dumps(defects, ensure_ascii=False)
new_d = f'var D={d_json};'
html, n = re.subn(r'var D=\[[\s\S]*?\];', new_d, html)
print(f"Defects replacement count: {n}")
if n == 0:
    print("WARNING: var D pattern not found! Trying alternative...")
    html = html.replace('var D=[];', new_d)

# Bake QA data
qa_json = json.dumps(qa_rows, ensure_ascii=False)
qa_ts_str = f'Auto-refreshed: {stamp} - {len(qa_rows)} QA records'
new_qa = f'var _bakedQA={qa_json};'
new_qa_ts = f"var _bakedQAts='{qa_ts_str}';"

if 'var _bakedQA=' in html:
    html, n1 = re.subn(r'var _bakedQA=\[[\s\S]*?\];', new_qa, html)
    html, n2 = re.subn(r'var _bakedQAts=.*?;', new_qa_ts, html)
    print(f"QA replacement count: {n1}, {n2}")
else:
    print("Inserting _bakedQA for first time...")
    insert = f'\n{new_qa}\n{new_qa_ts}\n'
    html = html.replace('var PRODUCTION', insert + 'var PRODUCTION')

# Update version stamp
ver = now.strftime('v%Y.%m.%d.%H:%M')
html = re.sub(r'v\d{4}\.\d{2}\.\d{2}\.\d{2}[:\-]\d{2}', ver, html)

# Write back
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"index.html size after bake: {len(html)} bytes")
print(f"Done! {len(defects)} defects, {len(qa_rows)} QA rows, stamp: {ver}")
