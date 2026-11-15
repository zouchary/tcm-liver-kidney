#!/usr/bin/env python3
"""v2 生成器：修复字段同行解析，重新生成 modules/ cases/ SKILL.md like-liver-kidney.md sources/"""
import re, json, os

with open('miyue_raw.md', encoding='utf-8') as f:
    lines = f.read().split('\n')

sections = [
    {'name': '肝炎肝硬化',      'start': 3,    'end': 550,  'prefix': '01_肝炎肝硬化', 'sec_num': '1'},
    {'name': '肝腹水',          'start': 551,  'end': 810,  'prefix': '02_肝腹水',     'sec_num': '2'},
    {'name': '胆囊炎胆石',      'start': 811,  'end': 984,  'prefix': '03_胆囊炎胆石', 'sec_num': '3'},
    {'name': '肾炎肾病尿毒症',  'start': 2459, 'end': 2726, 'prefix': '04_肾炎肾病',   'sec_num': '16'},
    {'name': '中风半身不遂',    'start': 3033, 'end': 3095, 'prefix': '05_中风',       'sec_num': '21'},
    {'name': '骨关节疾病',      'start': 3193, 'end': 3411, 'prefix': '06_骨关节',     'sec_num': '23'},
    {'name': '男性泌尿生殖',    'start': 6889, 'end': 7745, 'prefix': '07_男性泌尿',   'sec_num': '4'},
]

def parse_fields(block):
    """解析 [字段名] 值（同行）及后续延续行"""
    fields = {}
    current_key = None
    current_val = []
    for line in block.split('\n'):
        stripped = line.strip()
        m = re.match(r'^\[([^\]]+)\]\s*(.*)$', stripped)
        if m:
            if current_key and current_val:
                fields[current_key] = '\n'.join(current_val).strip()
            current_key = m.group(1)
            current_val = [m.group(2)] if m.group(2) else []
        elif current_key:
            current_val.append(stripped)
    if current_key and current_val:
        fields[current_key] = '\n'.join(current_val).strip()
    return fields

def clean(s):
    s = re.sub(r'\$[^$]*\$', '', s)
    s = s.replace('\\sim', '~')
    s = re.sub(r'\\[a-zA-Z]+', '', s)
    return s.strip()

def parse_prescriptions(text):
    parts = re.split(r'(?=^# \d+\.\d+[^\n]*)', text, flags=re.MULTILINE)
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.match(r'^# (\d+(?:\.\d+)?)\s+(.+?)(?:（(.+?)）)?$', p, re.MULTILINE)
        if m:
            num, name, source = m.groups()
            nl = p.find('\n')
            body = p[nl+1:] if nl > 0 else ''
            result.append({
                'num': num, 'name': name.strip(),
                'source': source.strip() if source else '',
                'fields': parse_fields(body)
            })
    return result

# 清空旧文件
os.makedirs('modules', exist_ok=True)
os.makedirs('cases', exist_ok=True)
os.makedirs('sources', exist_ok=True)
for d in ['modules', 'cases']:
    for f in os.listdir(d):
        if f.endswith('.md'):
            os.remove(os.path.join(d, f))

all_items = {}
per_section = {}

for sec in sections:
    chunk = '\n'.join(lines[sec['start']-1:sec['end']])
    items = parse_prescriptions(chunk)
    per_section[sec['name']] = items
    print(f"  [{sec['name']}] {len(items)}方")
    for item in items:
        key = f"{sec['sec_num']}-{item['num']}-{item['name']}"
        item['section'] = sec['name']
        all_items[key] = item

print(f"\n总计: {len(all_items)}方")

# ============ modules/ ============
for idx, (key, item) in enumerate(sorted(all_items.items()), 1):
    flds = item['fields']
    comp   = clean(flds.get('组成', '未详'))
    func   = clean(flds.get('功能', flds.get('功效', '未详')))
    main   = clean(flds.get('主治', '未详'))
    usage  = clean(flds.get('用法', '水煎服，日一剂'))
    an     = clean(flds.get('方解', ''))
    add    = clean(flds.get('加减', ''))
    note   = clean(flds.get('按语', ''))

    safe_name = re.sub(r'[^\w]', '', item['name'])[:20]
    fn = f"modules/{idx:02d}_{safe_name}.md"
    c = f"# {item['name']}\n\n"
    if item['source']:
        c += f"**来源**：{item['source']}  所属章节：{item['section']}\n\n"
    c += f"## 组成\n```\n{comp}\n```\n\n"
    c += f"## 功能\n{func}\n\n"
    c += f"## 主治\n{main}\n\n"
    c += f"## 用法\n{usage}\n\n"
    if an:   c += f"## 方解\n{an}\n\n"
    if add:  c += f"## 加减\n{add}\n\n"
    if note: c += f"## 按语\n{note}\n\n"
    c += "---\n"
    with open(fn, 'w', encoding='utf-8') as out:
        out.write(c)

mod_files = [f for f in os.listdir('modules') if f.endswith('.md')]
print(f"modules/ → {len(mod_files)}个文件")

# ============ cases/ ============
for sec in sections:
    for i, item in enumerate(per_section[sec['name']], 1):
        flds = item['fields']
        comp   = clean(flds.get('组成', ''))
        main   = clean(flds.get('主治', ''))
        func   = clean(flds.get('功能', flds.get('功效', '')))
        usage  = clean(flds.get('用法', '水煎服，日一剂'))
        an     = clean(flds.get('方解', ''))
        add    = clean(flds.get('加减', ''))
        note   = clean(flds.get('按语', ''))

        num_parts = item['num'].split('.')
        num_str = '_'.join(n.zfill(2) for n in num_parts)
        safe_name = re.sub(r'[^\w]', '', item['name'])[:20]
        fn = f"cases/{sec['prefix']}_{num_str}_{safe_name}.md"
        c = f"# {item['name']}\n\n"
        if item['source']:
            c += f"**来源**：{item['source']}\n\n"
        if main:  c += f"## 主治\n{main}\n\n"
        if comp:  c += f"## 组成\n```\n{comp}\n```\n\n"
        if func:  c += f"## 功能\n{func}\n\n"
        if usage: c += f"## 用法\n{usage}\n\n"
        if an:    c += f"## 方解\n{an}\n\n"
        if add:   c += f"## 加减\n{add}\n\n"
        if note:  c += f"## 按语\n{note}\n\n"
        with open(fn, 'w', encoding='utf-8') as out:
            out.write(c)

case_files = [f for f in os.listdir('cases') if f.endswith('.md')]
print(f"cases/ → {len(case_files)}个文件")

# ============ 校验示例 ============
print("\n=== 校验 modules/01 ===")
with open('modules/01_柴胡解毒汤.md', encoding='utf-8') as f:
    print(f.read())
