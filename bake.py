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

def extract_release_from_folder(folder):
    """Extract release from folder name e.g. '1.2 - DISCOUNT & BONUS' -> 'R1.2'"""
    if not folder: return ''
    m = re.match(r'^(\d+\.\d+[a-z]?)\s*[-\u2013\u2014]', str(folder).strip())
    if m: return 'R' + m.group(1)
    return ''
    """Replace var varname=[...]; using line-by-line search - works on any size"""
    marker = 'var ' + varname + '='
    idx = html.find(marker)
    if idx == -1:
        print('WARNING: ' + varname + ' not found - injecting...')
        inject = '\nvar ' + varname + '=' + new_json + ';\n'
        return html.replace('</script>', inject + '</script>', 1)
    
    # Find start of the value (after =)
    val_start = idx + len(marker)
    
    # Find end by looking for ;\nvar  or ;\n\n pattern after a reasonable chunk
    # Use json to find the exact end - parse from val_start
    chunk = html[val_start:]
    
    # Try to find end using json decoder
    try:
        decoder = json.JSONDecoder()
        obj, end_pos = decoder.raw_decode(chunk)
        # end_pos points to after the JSON value
        # skip optional ;
        actual_end = val_start + end_pos
        if actual_end < len(html) and html[actual_end] == ';':
            actual_end += 1
        result = html[:idx] + 'var ' + varname + '=' + new_json + ';' + html[actual_end:]
        print('  Replaced ' + varname + ': ' + str(len(html)) + ' -> ' + str(len(result)) + ' bytes')
        return result
    except Exception as e:
        print('  JSON decode failed for ' + varname + ': ' + str(e)[:100])
        # Last resort: inject after existing declaration
        inject = '\nvar ' + varname + '=' + new_json + ';\n'
        return html.replace('</script>', inject + '</script>', 1)

def replace_js_str_var(html, varname, new_value):
    pattern = "var " + varname + "='"
    idx = html.find(pattern)
    if idx == -1: return html
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
                # Always try folder-based release first
                folder_release = extract_release_from_folder(r.get('folder',''))
                r['release'] = folder_release if folder_release else (r.get('release') or release)
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
                    folder_release = extract_release_from_folder(r.get('folder',''))
                    r['release'] = folder_release if folder_release else release
                qa_summary.extend(rows2)
                print('  -> ' + str(len(rows2)) + ' summary rows')
    except Exception as e:
        print('  WARNING: ' + f + ': ' + str(e))

print('Total QA rows: ' + str(len(qa_rows)) + ', Summary: ' + str(len(qa_summary)))

with open('index.html', 'r', encoding='utf-8') as fh:
    html = fh.read()
print('Size before: ' + str(len(html)) + ' bytes')

html = safe_replace_var(html, 'D', json.dumps(defects, ensure_ascii=False))
html = safe_replace_var(html, '_bakedQA', json.dumps(qa_rows, ensure_ascii=False))
html = safe_replace_var(html, '_bakedQASummary', json.dumps(qa_summary, ensure_ascii=False))
html = replace_js_str_var(html, '_bakedQAts', 'Auto-refreshed: ' + stamp + ' - ' + str(len(qa_rows)) + ' QA records')

ver = now.strftime('v%Y.%m.%d.%H:%M')
html = re.sub(r'v\d{4}\.\d{2}\.\d{2}\.\d{2}[:\-]\d{2}', ver, html)

with open('index.html', 'w', encoding='utf-8') as fh:
    fh.write(html)

print('Size after: ' + str(len(html)) + ' bytes (' + str(len(html)//1024) + ' KB)')
print('Done! ' + str(len(defects)) + ' defects, ' + str(len(qa_rows)) + ' QA rows, ' + ver)
