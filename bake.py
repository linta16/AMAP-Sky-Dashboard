import json, glob, re
import pandas as pd
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
now = datetime.now(IST)
stamp = now.strftime('%d-%b-%y %H:%M')

def extract_release(filename):
    m = re.search(r'_(R[\d\.]+[a-z]?|UAT|SIT|regression)[\._]', filename, re.IGNORECASE)
    if m: return m.group(1).upper()
    m = re.search(r'_(R[\d\.]+[a-z]?|UAT|SIT)$', filename.replace('.xlsx','').replace('.csv',''), re.IGNORECASE)
    if m: return m.group(1).upper()
    return ''

def replace_js_var(html, varname, new_value):
    """Replace var varname=[...]; safely using marker-based approach"""
    marker_start = f'var {varname}=['
    idx = html.find(marker_start)
    if idx == -1:
        print(f"WARNING: {marker_start} not found!")
        return html
    # Find the matching closing ]; by tracking bracket depth
    start = idx + len(marker_start) - 1  # position of [
    depth = 0
    i = start
    while i < len(html):
        if html[i] == '[': depth += 1
        elif html[i] == ']':
            depth -= 1
            if depth == 0:
                # found closing ]
                end = i + 1  # position after ]
                if end < len(html) and html[end] == ';':
                    end += 1  # include ;
                break
        i += 1
    new_html = html[:idx] + f'var {varname}={new_value};' + html[end:]
    print(f"  Replaced {varname}: {len(html[:idx])} -> {len(new_html)} bytes")
    return new_html

def replace_js_str_var(html, varname, new_value):
    """Replace var varname='...'; """
    pattern = f"var {varname}='"
    idx = html.find(pattern)
    if idx == -1:
        print(f"WARNING: {pattern} not found!")
        return html
    start = idx + len(pattern)
    end = html.find("';", start)
    if end == -1: return html
    new_html = html[:idx] + f"var {varname}='{new_value}';" + html[end+2:]
    return new_html

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
qa_summary = []

for f in qa_files:
    print(f"Loading QA from: {f}")
    fname = f.split('/')[-1]
    test_type = 'uat' if 'uat' in fname.lower() else 'integration'
    release = extract_release(fname)
    print(f"  release={release}, type={test_type}")
    try:
        if f.lower().endswith('.csv'):
            df = pd.read_csv(f, encoding='utf-8-sig')
            df.columns = [c.strip().lower() for c in df.columns]
            rows = df.where(pd.notna(df), None).to_dict(orient='records')
            for r in rows:
                r['testType'] = test_type
                r['release'] = r.get('release', release)
                if 'linked defects' in r: r['defects'] = r['linked defects']
            qa_rows.extend(rows)
        else:
            xl = pd.ExcelFile(f)
            sheet_names = xl.sheet_names
            print(f"  Sheets: {sheet_names}")
            detail_sheet = next((s for s in sheet_names if 'detail' in s.lower()), sheet_names[0])
            df1 = pd.read_excel(f, sheet_name=detail_sheet)
            df1.columns = [c.strip().lower() for c in df1.columns]
            rows1 = df1.where(pd.notna(df1), None).to_dict(orient='records')
            for r in rows1:
                r['testType'] = test_type
                if not r.get('release'): r['release'] = release
                if 'linked defects' in r: r['defects'] = r['linked defects']
                if r.get('status'): r['status'] = str(r['status']).upper().strip()
            qa_rows.extend(rows1)
            print(f"  -> {len(rows1)} detailed rows")
            if len(sheet_names) > 1:
                summary_sheet = next((s for s in sheet_names if 'folder' in s.lower() or 'summary' in s.lower()), sheet_names[1])
                df2 = pd.read_excel(f, sheet_name=summary_sheet)
                df2.columns = [c.strip().lower() for c in df2.columns]
                rows2 = df2.where(pd.notna(df2), None).to_dict(orient='records')
                for r in rows2:
                    r['testType'] = test_type
                    r['release'] = release
                qa_summary.extend(rows2)
                print(f"  -> {len(rows2)} summary rows")
    except Exception as e:
        print(f"  WARNING: {f}: {e}")

print(f"Total QA rows: {len(qa_rows)}, Summary: {len(qa_summary)}")

# Read index.html
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()
print(f"Size before: {len(html)} bytes")

# Replace using bracket-depth matching — safe for large JSON with ]; inside
html = replace_js_var(html, 'D', json.dumps(defects, ensure_ascii=False))
html = replace_js_var(html, '_bakedQA', json.dumps(qa_rows, ensure_ascii=False))
html = replace_js_var(html, '_bakedQASummary', json.dumps(qa_summary, ensure_ascii=False))
html = replace_js_str_var(html, '_bakedQAts', f"Auto-refreshed: {stamp} - {len(qa_rows)} QA records")

# Update version stamp
ver = now.strftime('v%Y.%m.%d.%H:%M')
html = re.sub(r'v\d{4}\.\d{2}\.\d{2}\.\d{2}[:\-]\d{2}', ver, html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Size after: {len(html)} bytes ({len(html)//1024} KB)")
print(f"Done! {len(defects)} defects, {len(qa_rows)} QA rows, {ver}")
