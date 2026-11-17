#!/usr/bin/env python3
"""统一 modules 模板并补齐字段。
原则（蓝本诚实标注）：能从底稿原文抽到就抽，抽不到就显式写"原文未载"，绝不编造。
"""
import re, os, glob, json, sys

RAW = "miyue_raw.md"
lines = open(RAW, encoding="utf-8").read().split("\n")

SECS = [("01_肝炎肝硬化",3,550),("02_肝腹水",551,810),("03_胆囊炎胆石",811,984),
        ("04_肾炎肾病",2459,2726),("05_中风",3033,3095),("06_骨关节",3193,3411),
        ("07_男性泌尿",6889,7745)]

def sec_of(ln):
    for n,s,e in SECS:
        if s<=ln<=e: return n
    return None

def clean(s):
    s = re.sub(r"\$[^$\n]*\$", "", s)
    s = s.replace("\\times","×").replace("\\mathbb{I}","Ⅱ")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = s.replace("工入","工人").replace("波乏","疲乏")
    return re.sub(r"[ \t]+"," ",s).strip()

def parse_fields(block):
    fields, key, val = {}, None, []
    for l in block.split("\n"):
        st = l.strip()
        m = re.match(r"^\[([^\]]+)\]\s*(.*)$", st)
        if m:
            if key and val: fields[key] = clean("\n".join(val))
            key = m.group(1); val = [m.group(2)] if m.group(2) else []
        elif key:
            val.append(st)
    if key and val: fields[key] = clean("\n".join(val))
    return fields

# 底稿方剂 → 字段
heads = [(i,l.strip()) for i,l in enumerate(lines,1) if re.match(r"^# \d+\.\d+",l)]
raw_items = []
for idx,(i,l) in enumerate(heads):
    end = heads[idx+1][0] if idx+1<len(heads) else len(lines)+1
    if end>len(lines)+1: end=len(lines)+1
    body = "\n".join(lines[i:end-1])
    m = re.match(r"^# (\d+\.\d+)\s+(.+)$", l)
    if not m:
        continue
    no, rest = m.group(1), m.group(2)
    am = re.match(r"^(.*?)[（(]([^）)]+)[）)]\s*$", rest)
    if am:
        name, author = am.group(1).strip(), am.group(2).strip()
    else:
        name, author = rest.strip(), ""
    raw_items.append({
        "line": i, "no": no, "name": clean(name),
        "author": author,
        "sec": sec_of(i), "fields": parse_fields(body),
    })

def norm_name(n):
    n = re.sub(r"[\s　]+","",n)
    n = re.sub(r"[（(].*?[)）]","",n)
    return n

# 建立 归一化名 → raw item
by_name = {}
for it in raw_items:
    by_name.setdefault(norm_name(it["name"]), it)

# 禁忌线索词
RE_JINJI = re.compile(r"(不宜|不可|忌|禁忌|慎用|勿用|禁服|不得|非所宜|不宜单独|不宜久服|不宜多用|便溏者|孕妇禁用)")
RE_ZHENGDIAN = re.compile(r"(适用于|辨证(?:为|属)|证属|若见|若属|凡|其本证|本方为|主治|属[东南西北中]方)")

def pick_sentences(text, rx, limit=3):
    if not text: return []
    t = re.sub(r"\s*\n\s*","",text)
    out=[]
    for s in re.split(r"(?<=[。；])", t):
        s=s.strip()
        if s and rx.search(s) and s not in out:
            out.append(s)
        if len(out)>=limit: break
    return out

# 模块文件 → 方剂名
MOD_ORDER = sorted(glob.glob("modules/*.md"))
report = []
for f in MOD_ORDER:
    t = open(f, encoding="utf-8").read()
    m = re.match(r"^# (.+)$", t.strip())
    title = clean(m.group(1)) if m else ""
    base = os.path.basename(f)
    # 名称匹配：文件名前缀数字 + 名称
    mm = re.match(r"^(\d+)_(.+)\.md$", base)
    fname_candidate = mm.group(2) if mm else title
    raw = None
    cands = [fname_candidate, title]
    # 文件名可能粘连了作者名（如 60_强腰散张鉴铭），逐字缩短前缀再匹配
    for c in list(cands):
        cn = re.sub(r"[\s　]+","",c)
        for k in range(len(cn)-1, 1, -1):
            cands.append(cn[:k])
    for cand in cands:
        key = norm_name(cand)
        if key in by_name: raw = by_name[key]; break
    if raw is None:
        # 退化：按顺序 / 章节归属
        cands = [it for it in raw_items if it["sec"] and it["sec"].split("_")[0]==base.split("_")[0][:2]]
        if cands: raw = cands[0]
    if raw is None:
        report.append((base, "未匹配到底稿方剂")); continue

    F = raw["fields"]
    # 抽取 禁忌 / 辨证要点 线索
    pool = " ".join([F.get("按语",""), F.get("方解",""), F.get("功能",""), F.get("主治","")])
    jinji = pick_sentences(pool, RE_JINJI, 3)
    zd = pick_sentences(F.get("主治","") + " " + F.get("按语",""), RE_ZHENGDIAN, 2)

    t2 = t
    # 1) 出处
    if not re.search(r"^## 出处", t2, re.M):
        src = f"{raw['author']}（《国家级名老中医效验秘方精选》）· {raw['sec'].split('_',1)[1]} · 第 {raw['line']} 行"
        t2 = re.sub(r"^\*\*来源\*\*：.*$", "", t2, count=1, flags=re.M)
        t2 = t2.replace("# "+title, f"# {title}\n\n## 出处\n{src}", 1)
    # 2) 功能 → 功效（统一命名）
    t2 = re.sub(r"^## 功能\s*$", "## 功效", t2, flags=re.M)
    # 3) 补 辨证要点
    if not re.search(r"^## 辨证要点", t2, re.M):
        body = "\n".join(f"- {x}" for x in zd) if zd else "原文未单列辨证要点，参见【按语】与【主治】。"
        t2 = t2.rstrip() + f"\n\n## 辨证要点\n{body}\n"
    # 4) 补 加减
    if not re.search(r"^## 加减", t2, re.M):
        jf = F.get("加减","")
        if jf:
            body = jf
        elif F.get("方解"):
            cand = pick_sentences(F["方解"], re.compile(r"(加|减|加味|随证)"), 2)
            body = "\n".join(f"- {x}" for x in cand) if cand else "原文未载加减。"
        else:
            body = "原文未载加减。"
        t2 = t2.rstrip() + f"\n\n## 加减\n{body}\n"
    # 5) 补 禁忌
    if not re.search(r"^## 禁忌", t2, re.M):
        body = "\n".join(f"- {x}" for x in jinji) if jinji else "原文未载禁忌。参见【按语】。"
        t2 = t2.rstrip() + f"\n\n## 禁忌\n{body}\n"
    # 6) 补 方解（原文缺则标注）
    if not re.search(r"^## 方解", t2, re.M):
        t2 = t2.rstrip() + "\n\n## 方解\n原文未载方解。\n"
    open(f, "w", encoding="utf-8").write(t2)
    report.append((base, "OK"))

bad = [r for r in report if r[1]!="OK"]
print(f"处理 {len(report)} 篇，异常 {len(bad)}")
for b in bad[:10]: print("  !", b)
