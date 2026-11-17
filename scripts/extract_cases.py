#!/usr/bin/env python3
"""从底稿抽取真医案，输出 证-机-方-效 四段链 + 原文溯源。
蓝本: tcm-distiller references/13-cases-guide.md
铁律:
  1. 四段链内容必须来自原文句子，逐字引用，不做推理补全
  2. 疗效缺记录 → 写"未见疗效记录"
  3. 剂量按原文记录，不换算
  4. 来源标注 文件 搜"关键词" + 行号
"""
import re, os, json, sys, glob, hashlib

MIDX = json.load(open("scripts/module_index.json", encoding="utf-8")) if os.path.exists("scripts/module_index.json") else {"by_fno": {}}

def module_ref(fno, fname):
    """按方剂编号定位 modules 文件；编号重号时按方名消歧（底稿 23.7 重号实为底稿编号错误）"""
    cands = MIDX.get("by_fno", {}).get(fno, [])
    if not cands: return None
    if len(cands) == 1: return cands[0]["file"]
    for c in cands:
        if c["name"].strip() == fname.strip(): return c["file"]
    return cands[0]["file"]

RAW = "miyue_raw.md"
OUT = "cases"
lines = open(RAW, encoding="utf-8").read().split("\n")

SECS = [
    ("01_肝炎肝硬化", 3, 550), ("02_肝腹水", 551, 810),
    ("03_胆囊炎胆石", 811, 984), ("04_肾炎肾病", 2459, 2726),
    ("05_中风", 3033, 3095), ("06_骨关节", 3193, 3411),
    ("07_男性泌尿", 6889, 7745),
]

def sec_of(ln):
    for name, s, e in SECS:
        if s <= ln <= e: return name
    return None

heads = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.match(r"^# \d+\.\d+", l)]
def owner(ln):
    prev = None
    for i, l in heads:
        if i <= ln: prev = (i, l)
        else: break
    return prev

def clean(s):
    s = re.sub(r"\$[^$\n]*\$", "", s)
    s = s.replace("\\times", "×").replace("\\mathbb{I}", "Ⅱ")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = s.replace("工入", "工人").replace("波乏", "疲乏")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def block_after(start_ln):
    txt = []
    for i in range(start_ln, len(lines) + 1):
        l = lines[i - 1].rstrip()
        if i > start_ln and re.match(r"^# \d", l): break
        if i > start_ln and re.match(r"^\[[^]]*\]", l.strip()): break
        if i > start_ln and re.search(r"^(附\s*\S*简介|通讯地址)", l.strip()): break
        txt.append(l)
        if len(txt) > 300: break
    return clean("\n".join(txt).strip())

# 句级分类
RE_ZHENG = re.compile(r"(中医辨证|辨证为|辨证属|辨为|证属|辨证)")
RE_FANG  = re.compile(r"(予|处方[:：]|为疏|投|服上方|拟方|用本方|方[:：]|加味|合用)")
RE_XIAO  = re.compile(r"(好转|痊愈|显效|有效|无效|消失|减轻|改善|恢复|复查|随访|未再|未复发|巩固|治愈|日?渐好转|症减)")
RE_JI    = re.compile(r"(病机|所致|因[为是]|病在|病位|属[于為]?[^，。]{0,8}虚|湿热|气滞|血瘀|阴虚|阳虚|脾虚|肝郁|肝肾)")

def sentences(t):
    t = re.sub(r"\s*\n\s*", "", t)
    parts = re.split(r"(?<=[。；])", t)
    return [p.strip() for p in parts if p.strip()]

def pick(sents, regex, limit=4):
    out = []
    for s in sents:
        if regex.search(s) and s not in out:
            out.append(s)
        if len(out) >= limit: break
    return out

def build_chain(first, body):
    sents = sentences(body)
    # 证：优先"中医辨证为…"整句
    zheng = pick(sents, RE_ZHENG, 2)
    # 机：含病机/因/病在等，但排除已被判为证的句子
    ji = [s for s in pick(sents, RE_JI, 8) if s not in zheng]
    # 方：处方句
    fang = pick(sents, RE_FANG, 3)
    # 效：疗效句
    xiao = [s for s in pick(sents, RE_XIAO, 4) if s not in fang]
    return zheng, ji, fang, xiao

cases = []
for i, l in enumerate(lines, 1):
    m = re.match(r"^\[(?:典型病例|案例)\]\s*(.*)$", l.strip())
    if not m: continue
    sec = sec_of(i)
    if not sec: continue
    raw_first = m.group(1)
    first = clean(raw_first)
    owner_ln, owner_txt = owner(i)
    fm = re.match(r"^# (\d+\.\d+)\s+(.+?)(?:（(.+?)）)?\s*$", owner_txt)
    fno = fm.group(1) if fm else "?"
    fname = clean(fm.group(2)) if fm else owner_txt
    fauthor = (fm.group(3) or "").strip() if fm else ""
    body = block_after(i + 1)
    zheng, ji, fang, xiao = build_chain(first, body)
    digest = hashlib.md5((first + body[:80]).encode()).hexdigest()[:6]
    cases.append(dict(sec=sec, line=i, first=first, raw_first=raw_first, body=body, fno=fno,
                      fname=fname, fauthor=fauthor, digest=digest,
                      zheng=zheng, ji=ji, fang=fang, xiao=xiao))

os.makedirs(OUT, exist_ok=True)
for f in glob.glob(f"{OUT}/[0-9][0-9]_*.md"):
    os.remove(f)

def seg(title, items, miss):
    if not items: return f"## {title}\n\n{miss}\n"
    return f"## {title}\n\n" + "\n".join(f"- {x}" for x in items) + "\n"

rows = []
for c in cases:
    sec_no = c["sec"].split("_")[0]
    sec_cn = c["sec"].split("_", 1)[1]
    fn = f"{sec_no}_case-{c['first'][0]}{c['digest']}.md"
    md = f"""# 医案：{c['fname']}（{c['first']}）

**章节**：{sec_cn}
**来源方剂**：{c['fno']} {c['fname']}（{c['fauthor']}）
**出处**：《国家级名老中医效验秘方精选》·{c['fname']} 条 [典型病例]
**溯源**：`miyue_raw.md` 搜"{c['raw_first'][:12]}"（第 {c['line']} 行）

{seg("证", c["zheng"], "原文未载明确证型。")}
{seg("机", c["ji"], "原文未单独论述病机。")}
{seg("方", c["fang"], "原文仅记方名，组成见 `" + (module_ref(c["fno"], c["fname"]) or "modules/（未定位）") + "`。")}
{seg("效", c["xiao"], "未见疗效记录。")}

## 原文摘录

> {c['first']}
>
{c['body']}
"""
    open(f"{OUT}/{fn}", "w", encoding="utf-8").write(md)
    rows.append((sec_cn, c["first"], c["fname"], c["fauthor"], c["line"], fn, c))

with open(f"{OUT}/00_index.md", "w", encoding="utf-8") as f:
    f.write("# 医案库索引\n\n")
    f.write(f"> 共 {len(rows)} 则真医案，逐条溯源至 `miyue_raw.md` 底稿行号。\n")
    f.write("> 四段链内容逐字取自原文；原文未载者显式标注，未作推理补全（诚实标注规范）。\n\n")
    f.write("| 章节 | 患者 | 使用方剂 | 作者 | 底稿行号 | 文件 |\n")
    f.write("|------|------|---------|------|---------|------|\n")
    for sec_cn, first, fname, fauthor, ln, fn, _ in rows:
        f.write(f"| {sec_cn} | {first[:24]} | {fname} | {fauthor} | L{ln} | `{fn}` |\n")
    f.write("\n> 检索：患者主诉/病名 → 查本表定位章节与方剂 → Read 对应医案文件。\n")

json.dump([{k: v for k, v in c.items() if k != "body"} for c in cases],
          open("scripts/cases_extracted.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"cases={len(cases)}  files={len(glob.glob(f'{OUT}/[0-9][0-9]_*.md'))}")
