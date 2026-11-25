#!/usr/bin/env python3
"""改写稿和原稿逐字稿的相似度检查（爆款改写工作流第 6 步）。

用法：
  python3 similarity_check.py --mine <改写稿.md> --source <爆款笔记.md> [--source ...]
                              [--ignore 词 ...] [--max-overlap 20] [--max-run 8] [--n 5]

取文本：
  - 原稿：有「## 逐字稿」一节就只取这一节，否则取全文。
  - 改写稿：有「## 口播全文」一节就只取这一节；否则取所有表头含「口播」的表格里那一列；
    都没有就取全文。
  - 去掉时间点 [00:00]、〔编·待换〕之类的标记、标点和空白；--ignore 的词整体去掉。

两个指标（都按「原稿 → 改写稿」算，每条原稿单独比）：
  - 重合率：改写稿里有多少字落在「和原稿相同的连续 n 个字」里（默认 n=5）。
  - 最长相同片段：改写稿和原稿最长的一段连续相同文字。
过线：重合率 < max-overlap（默认 20%），且最长相同片段 < max-run（默认 8 个字）。
全部原稿都过线，退出码 0；否则 1。
"""
import argparse
import re
import sys

KEEP = re.compile(r"[一-鿿A-Za-z0-9]")


def section(text, title):
    m = re.search(rf"^##\s*{re.escape(title)}[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(1) if m else None


def table_column(text, name):
    out, col = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            col = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if col is None:
            hits = [i for i, c in enumerate(cells) if name in c]
            col = hits[0] if hits else None
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if col < len(cells):
            out.append(cells[col])
    return "\n".join(out) if out else None


def normalize(text, ignore):
    text = re.sub(r"\[\d{1,2}:\d{2}(?:[.:]\d+)?\]", "", text)
    text = re.sub(r"〔[^〕]*〕", "", text)
    text = text.lower()
    for w in ignore:
        text = text.replace(w.lower(), "")
    return "".join(KEEP.findall(text))


def overlap(mine, src, n):
    grams = {src[i:i + n] for i in range(len(src) - n + 1)}
    covered = [False] * len(mine)
    for i in range(len(mine) - n + 1):
        if mine[i:i + n] in grams:
            for j in range(i, i + n):
                covered[j] = True
    return sum(covered) / len(mine) * 100 if mine else 0.0


def common_runs(mine, src, min_len):
    """返回 (最长长度, 最长片段, 所有 >= min_len 的相同片段)。"""
    best, best_end = 0, 0
    prev = [0] * (len(src) + 1)
    ends = {}
    for i in range(1, len(mine) + 1):
        cur = [0] * (len(src) + 1)
        a = mine[i - 1]
        for j in range(1, len(src) + 1):
            if a == src[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best, best_end = cur[j], i
        # 记录在 i 处结束、且不能再往后延长的片段
        prev = cur
        for j in range(1, len(src) + 1):
            if cur[j] >= min_len:
                ends[i] = max(ends.get(i, 0), cur[j])
    runs = set()
    for i, L in ends.items():
        if i + 1 not in ends or ends[i + 1] != L + 1:
            runs.add(mine[i - L:i])
    return best, mine[best_end - best:best_end], sorted(runs, key=len, reverse=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mine", required=True)
    ap.add_argument("--source", required=True, action="append")
    ap.add_argument("--ignore", action="append", default=[])
    ap.add_argument("--max-overlap", type=float, default=20.0)
    ap.add_argument("--max-run", type=int, default=8)
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()

    raw = open(a.mine, encoding="utf-8").read()
    mine_text = section(raw, "口播全文") or table_column(raw, "口播") or raw
    mine = normalize(mine_text, a.ignore)
    if not mine:
        sys.exit("改写稿里没取到文字：请检查「## 口播全文」一节或表格里的「口播」列。")
    print(f"改写稿：{len(mine)} 字（已去掉标点、时间点和标记）")

    ok_all = True
    for path in a.source:
        sraw = open(path, encoding="utf-8").read()
        src = normalize(section(sraw, "逐字稿") or sraw, a.ignore)
        if not src:
            print(f"\n原稿 {path}：没取到文字，跳过")
            ok_all = False
            continue
        ov = overlap(mine, src, a.n)
        best, best_txt, runs = common_runs(mine, src, a.max_run)
        ok = ov < a.max_overlap and best < a.max_run
        ok_all &= ok
        print(f"\n原稿：{path}（{len(src)} 字）")
        print(f"  重合率：{ov:.1f}%（要求 < {a.max_overlap:g}%）{'✓' if ov < a.max_overlap else '✗'}")
        print(f"  最长相同片段：{best} 字「{best_txt}」（要求 < {a.max_run} 字）{'✓' if best < a.max_run else '✗'}")
        if runs:
            print(f"  连续 {a.max_run} 字以上相同的片段（要改）：")
            for r in runs[:20]:
                print(f"    -「{r}」")
        print(f"  结论：{'过线' if ok else '不过线'}")
    print(f"\n总结论：{'全部过线' if ok_all else '有原稿不过线，改完重跑'}")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
