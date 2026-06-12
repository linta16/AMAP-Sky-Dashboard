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

def replace_js_var(html, varname, new_json):
    """Replace var varname=[...]; handling strings with ]; inside them"""
    marker = 'var ' + varname + '=['
    idx = html.find(marker)
    if idx == -1:
        print('WARNING: ' + marker + ' not found!')
        return html
    start = idx + len(marker) - 1  # position of [
    depth = 0
    in_string = False
    string_char = ''
    escape_next = False
    end = -1
    i = start
    while i < len(html):
        c = html[i]
        if escape_next:
            escape_next = False
        elif c == '\\' and in_string:
            escape_next = True
        elif in_string:
            if c == string_char:
                in_string = False
        elif c in ('"', "'"):
            in_string = True
            string_char = c
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                end = i + 2  # skip ];
                break
        i += 1
    if end == -1:
        print('WARNING: Could not find end of ' + varname + ' - trying fallback')
        # Fallback: find var varname= and replace until next \nvar 
        start2 = html.find('var ' + varname + '=')
        end2 = html.find('\nvar ', start2 + 1)
        if end2 == -1: end2 = html.find('\n\n', start2 + 1)
        if start2 != -1 and end2 != -1:
            result = html[:start2] + 'var ' + varname + '=' + new_json + ';\n' + html[end2+1:]
            print('  Fallback replaced ' + varname + ': ' + str(len(html)) + ' -> ' + str(len(result)))
            return result
        return html
    result = html[:idx] + 'var ' + varname + '=' + new_json + ';' + html[end:]
    print('  Replaced ' + varname + ': ' + str(len(html)) + ' -> ' + str(len(result)) + ' bytes')
    return result

def replace_js_str_var(html, varname, new_value):
    pattern = "var " + varname + "='"
    idx = html.find(pattern)
    if idx == -1:
        print('WARNING: ' + pattern + ' not found!')
        return html
    start = idx + len(pattern)
    end = html.find("';", start)
    if end == -1: return html
    return html[:idx] + "var " + varname + "='" + new_value + "';" + html[end+2:]

# Read Defects
defect_files = sorted(glob.glob('data/defects/*.csv') + glob.glob('data/defects/*.CSV'))
defects = []
if defect_files:
    latest = defect_files[-1]
    print('Loading defects from: ' + latest)
    df = pd.read_csv(latest, encoding='utf-8-sig')
    df.columns = [c.strip().lower() for c in df.columns]
    defects = df.where(pd.notna(df), None).to_dict(orient='records')
    print('Loaded ' + str(len(defects)) + ' defect rows')

# Read QA files
qa_files = sorted(
    glob.glob('data/qa/*.csv') + glob.glob('data/qa/*.CSV') +
    glob.glob('data/qa/*.xlsx') + glob.glob('data/qa/*.XLSX')
)
qa_rows = []
qa_summary = []

for f in qa_files:
    print('Loading QA from: ' + f)
    fname = f.split('/')[-1]
    test_type = 'uat' if 'uat' in fname.lower() else 'integration'
    release = extract_release(fname)
    print('  release=' + release + ', type=' + test_type)
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
            print('  Sheets: ' + str(sheet_names))
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
            print('  -> ' + str(len(rows1)) + ' detailed rows')
            if len(sheet_names) > 1:
                summary_sheet = next((s for s in sheet_names if 'folder' in s.lower() or 'summary' in s.lower()), sheet_names[1])
                df2 = pd.read_excel(f, sheet_name=summary_sheet)
                df2.columns = [c.strip().lower() for c in df2.columns]
                rows2 = df2.where(pd.notna(df2), None).to_dict(orient='records')
                for r in rows2:
                    r['testType'] = test_type
                    r['release'] = release
                qa_summary.extend(rows2)
                print('  -> ' + str(len(rows2)) + ' summary rows')
    except Exception as e:
        print('  WARNING: ' + f + ': ' + str(e))

print('Total QA rows: ' + str(len(qa_rows)) + ', Summary: ' + str(len(qa_summary)))

with open('index.html', 'r', encoding='utf-8') as fh:
    html = fh.read()
print('Size before: ' + str(len(html)) + ' bytes')

html = replace_js_var(html, 'D', json.dumps(defects, ensure_ascii=False))
html = replace_js_var(html, '_bakedQA', json.dumps(qa_rows, ensure_ascii=False))
html = replace_js_var(html, '_bakedQASummary', json.dumps(qa_summary, ensure_ascii=False))
html = replace_js_str_var(html, '_bakedQAts', 'Auto-refreshed: ' + stamp + ' - ' + str(len(qa_rows)) + ' QA records')

ver = now.strftime('v%Y.%m.%d.%H:%M')
html = re.sub(r'v\d{4}\.\d{2}\.\d{2}\.\d{2}[:\-]\d{2}', ver, html)

with open('index.html', 'w', encoding='utf-8') as fh:
    fh.write(html)

print('Size after: ' + str(len(html)) + ' bytes (' + str(len(html)//1024) + ' KB)')
print('Done! ' + str(len(defects)) + ' defects, ' + str(len(qa_rows)) + ' QA rows, ' + ver)
