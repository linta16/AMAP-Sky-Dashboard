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

# Read QA files — read both sheets from each Excel file
qa_files = sorted(
    glob.glob('data/qa/*.csv') + glob.glob('data/qa/*.CSV') +
    glob.glob('data/qa/*.xlsx') + glob.glob('data/qa/*.XLSX')
)
qa_rows = []        # from Detailed Results sheet
qa_summary = []     # from Folder Summary sheet

for f in qa_files:
    print(f"Loading QA from: {f}")
    test_type = 'uat' if 'uat' in f.lower() else 'integration'
    try:
        if f.lower().endswith('.csv'):
            df = pd.read_csv(f, encoding='utf-8-sig')
            df.columns = [c.strip().lower() for c in df.columns]
            rows = df.where(pd.notna(df), None).to_dict(orient='records')
            for r in rows: r['testType'] = test_type
            qa_rows.extend(rows)
            print(f"  -> {len(rows)} rows [{test_type}]")
        else:
            xl = pd.ExcelFile(f)
            sheet_names = xl.sheet_names
            print(f"  Sheets: {sheet_names}")

            # Read Detailed Results sheet
            detail_sheet = next((s for s in sheet_names if 'detail' in s.lower()), sheet_names[0])
            df1 = pd.read_excel(f, sheet_name=detail_sheet)
            df1.columns = [c.strip().lower() for c in df1.columns]
            rows1 = df1.where(pd.notna(df1), None).to_dict(orient='records')
            for r in rows1: r['testType'] = test_type
            qa_rows.extend(rows1)
            print(f"  -> {len(rows1)} detailed rows [{test_type}]")

            # Read Folder Summary sheet
            if len(sheet_names) > 1:
                summary_sheet = next((s for s in sheet_names if 'folder' in s.lower() or 'summary' in s.lower()), sheet_names[1])
                df2 = pd.read_excel(f, sheet_name=summary_sheet)
                df2.columns = [c.strip().lower() for c in df2.columns]
                rows2 = df2.where(pd.notna(df2), None).to_dict(orient='records')
                for r in rows2:
                    r['testType'] = test_type
                    r['_sheetType'] = 'folder_summary'
                qa_summary.extend(rows2)
                print(f"  -> {len(rows2)} folder summary rows [{test_type}]")

    except Exception as e:
        print(f"  WARNING: {f}: {e}")

print(f"Total detailed rows: {len(qa_rows)}")
print(f"Total folder summary rows: {len(qa_summary)}")

# Read index.html
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f"Size before: {len(html)} bytes")

# Bake using simple string replace
d_json = json.dumps(defects, ensure_ascii=False)
qa_json = json.dumps(qa_rows, ensure_ascii=False)
qa_summary_json = json.dumps(qa_summary, ensure_ascii=False)
qa_ts = f"Auto-refreshed: {stamp} - {len(qa_rows)} QA records"

html = html.replace('var D=[];', f'var D={d_json};', 1)
html = html.replace('var _bakedQA=[];', f'var _bakedQA={qa_json};', 1)
html = html.replace("var _bakedQAts='';", f"var _bakedQAts='{qa_ts}';", 1)

# Bake folder summary if variable exists
if 'var _bakedQASummary=[];' in html:
    html = html.replace('var _bakedQASummary=[];', f'var _bakedQASummary={qa_summary_json};', 1)
    print("Folder summary baked!")

# Update version stamp
ver = now.strftime('v%Y.%m.%d.%H:%M')
html = re.sub(r'v\d{4}\.\d{2}\.\d{2}\.\d{2}[:\-]\d{2}', ver, html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Size after: {len(html)} bytes ({len(html)//1024} KB)")
print(f"Done! {len(defects)} defects, {len(qa_rows)} QA rows, {ver}")
