import json, glob, re
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
        df = pd.read_csv(f, encoding='utf-8-sig') if f.lower().endswith('.csv') else pd.read_excel(f)
        df.columns = [c.strip().lower() for c in df.columns]
        rows = df.where(pd.notna(df), None).to_dict(orient='records')
        qa_rows.extend(rows)
        print(f"  -> {len(rows)} rows")
    except Exception as e:
        print(f"  WARNING: {f}: {e}")

print(f"Total QA rows: {len(qa_rows)}")

# Read index.html
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f"Size before: {len(html)} bytes")

# Use simple string replace - guaranteed to work
d_json = json.dumps(defects, ensure_ascii=False)
qa_json = json.dumps(qa_rows, ensure_ascii=False)
qa_ts = f"Auto-refreshed: {stamp} - {len(qa_rows)} QA records"

html = html.replace('var D=[];', f'var D={d_json};', 1)
html = html.replace('var _bakedQA=[];', f'var _bakedQA={qa_json};', 1)
html = html.replace("var _bakedQAts='';", f"var _bakedQAts='{qa_ts}';", 1)

# Update version stamp
ver = now.strftime('v%Y.%m.%d.%H:%M')
html = re.sub(r'v\d{4}\.\d{2}\.\d{2}\.\d{2}[:\-]\d{2}', ver, html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Size after: {len(html)} bytes ({len(html)//1024} KB)")
print(f"Done! {len(defects)} defects, {len(qa_rows)} QA rows, {ver}")
