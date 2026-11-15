#!/usr/bin/env python3
"""从底稿 miyue_raw.md 可复现地重建 modules/（统一模板 + 补齐字段）。
模板字段顺序固定：出处 / 组成 / 功效 / 主治 / 辨证要点 / 用法 / 方解 / 加减 / 禁忌 / 按语
诚实标注原则（蓝本 S10）：原文未载者写"原文未载…"，绝不编造。
"""
import re, os, glob, shutil

RAW = "miyue_raw.md"
lines = open(RAW, encoding="utf-8").read().split("\n")

SECTIONS = [
    {"name": "肝炎肝硬化",     "start": 3,    "end": 550,  "prefix": "01_肝炎肝硬化", "sec_num": "1"},
    {"name": "肝腹水",         "start": 551,  "end": 810,  "prefix": "02_肝腹水",     "sec_num": "2"},
    {"name": "胆囊炎胆石",     "start": 811,  "end": 984,  "prefix": "03_胆囊炎胆石", "sec_num": "3"},
    {"name": "肾炎肾病尿毒症", "start": 2459, "end": 2726, "prefix": "04_肾炎肾病",   "sec_num": "16"},
    {"name": "中风半身不遂",   "start": 3033, "end": 3095, "prefix": "05_中风",       "sec_num": "21"},
    {"name": "骨关节疾病",     "start": 3193, "end": 3411, "prefix": "06_骨关节",     "sec_num": "23"},
    {"name": "男性泌尿生殖",   "start": 6889, "end": 7745, "prefix": "07_男性泌尿",   "sec_num": "4"},
]

def clean(s):
    s = re.sub(r"\$[^$\n]*\$", "", s)
    s = s.replace("\\times", "×").replace("\\mathbb{I}", "Ⅱ")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = s.replace("工入", "工人").replace("波乏", "疲乏")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def parse_fields(block):
    fields, key, val = {}, None, []
    for l in block.split("\n"):
        st = l.strip()
        m = re.match(r"^\[([^\]]+)\]\s*(.*)$", st)
        if m:
            if key and val: fields[key] = clean("\n".join(val))
            key, val = m.group(1), ([m.group(2)] if m.group(2) else [])
        elif key:
            val.append(st)
    if key and val: fields[key] = clean("\n".join(val))
    return fields

def parse_prescriptions(text):
    parts = re.split(r"(?=^# \d+\.\d+[^\n]*)", text, flags=re.MULTILINE)
    out = []
    for p in parts:
        p = p.strip()
        if not p: continue
        m = re.match(r"^# (\d+\.\d+)\s+(.+)$", p, flags=re.MULTILINE)
        if not m: continue
        no, rest = m.group(1), m.group(2)
        am = re.match(r"^(.*?)[（(]([^）)]+)[）)]\s*$", rest)
        name, author = (am.group(1).strip(), am.group(2).strip()) if am else (rest.strip(), "")
        nl = p.find("\n")
        body = p[nl+1:] if nl > 0 else ""
        out.append({"num": no, "name": name, "author": author, "fields": parse_fields(body),
                    "line": text[:text.find(p)].count("\n") + 1})
    return out

all_items, per_section, line_of = {}, [], {}
for sec in SECTIONS:
    chunk = "\n".join(lines[sec["start"]-1:sec["end"]])
    items = parse_prescriptions(chunk)
    for it in items:
        it["section"] = sec["name"]
        all_items[f"{sec['sec_num']}-{it['num']}-{it['name']}"] = it
    per_section.append((sec, items))

RE_JINJI = re.compile(r"(不宜|不可|忌|慎用|勿用|禁服|不得|非所宜|孕妇禁用|便溏者)")
RE_ZD = re.compile(r"(适用于|中医辨证|辨证为|证属|本方为|适用于|凡)")
RE_JI = re.compile(r"(病机|因[为是]|病在|湿热|气滞|血瘀|阴虚|阳虚|脾虚|肝郁)")

def sentences(text):
    if not text: return []
    t = re.sub(r"\s*\n\s*", "", text)
    return [s.strip() for s in re.split(r"(?<=[。；])", t) if s.strip()]

def pick(text, rx, limit=3):
    out = []
    for s in sentences(text):
        if rx.search(s) and s not in out: out.append(s)
        if len(out) >= limit: break
    return out

os.makedirs("modules", exist_ok=True)
for f in glob.glob("modules/*.md"): os.remove(f)

idx_map = {}
for idx, (key, it) in enumerate(sorted(all_items.items()), 1):
    F = it["fields"]
    safe = re.sub(r"[^\w一-鿿]", "", it["name"])[:20]
    fn = f"modules/{idx:02d}_{safe}.md"
    idx_map[key] = fn

    comp  = F.get("组成", "") or "原文未载组成。"
    func  = F.get("功能", F.get("功效", "")) or "原文未载功效。"
    main  = F.get("主治", "") or "原文未载主治。"
    usage = F.get("用法", "") or "原文未载用法。"
    an    = F.get("方解", "") or "原文未载方解。"
    add   = F.get("加减", "") or ""
    note  = F.get("按语", "") or "原文未载按语。"

    pool = " ".join([note, an, func, main])
    jinji = pick(pool, RE_JINJI, 3)
    zd = pick(main + " " + note, RE_ZD, 2)
    if not add:
        cand = pick(an, re.compile(r"(加减|加味|随证|若见)"), 2)
        add = "\n".join(f"- {x}" for x in cand) if cand else "原文未载加减。"

    src = f"{it['author']}（《国家级名老中医效验秘方精选》）· {it['section']} · {it['num']} 条"
    c = f"# {it['name']}\n\n## 出处\n{src}\n\n"
    c += f"## 组成\n```\n{comp}\n```\n\n"
    c += f"## 功效\n{func}\n\n"
    c += f"## 主治\n{main}\n\n"
    c += "## 辨证要点\n" + ("\n".join(f"- {x}" for x in zd) if zd else "原文未单列辨证要点，参见【主治】【按语】。") + "\n\n"
    c += f"## 用法\n{usage}\n\n"
    c += f"## 方解\n{an}\n\n"
    c += f"## 加减\n{add}\n\n"
    c += "## 禁忌\n" + ("\n".join(f"- {x}" for x in jinji) if jinji else "原文未载禁忌，参见【按语】。") + "\n\n"
    c += f"## 按语\n{note}\n"
    open(fn, "w", encoding="utf-8").write(c)

import json
by_fno = {}
for k, v in idx_map.items():
    by_fno.setdefault(k.split("-")[1], []).append({"name": k.split("-", 2)[2], "file": v})
json.dump({"index": idx_map, "by_fno": by_fno},
          open("scripts/module_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"modules 重建完成：{len(idx_map)} 篇")
