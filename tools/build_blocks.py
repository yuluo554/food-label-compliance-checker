"""条文块切分工具（M3）：data/knowledge/raw/_extracted/*.txt → data/knowledge/blocks/*.json

切分口径（plan/05 §1.1 L2 层：块号+条款号+原文+出处+status）：

1. 输入是官方 PDF 的提取文本（保留 `=== PAGE n ===` 分页标记，块记页码）。
   重新提取命令（需 PyMuPDF，非运行期依赖；提取文本随仓入库，重跑仅在
   PDF 更换时需要）：
     py -X utf8 - <<'PY'
     import fitz
     for n in ['gb7718-2011','gb7718-2025','gb28050-2011','gb28050-2025']:
         doc = fitz.open(f'data/knowledge/raw/{n}.pdf')
         t = '\\n'.join(f'=== PAGE {i+1} ===\\n' + p.get_text('text')
                       for i, p in enumerate(doc))
         open(f'data/knowledge/raw/_extracted/{n}.txt', 'w',
              encoding='utf-8', newline='\\n').write(t)
     PY
2. 行归并：2025 版 PDF 把条号拆行（"4." / "2." / "1 应在…"），把「上一行为
   『可选≤等前缀+纯数字+句点』且本行以数字开头」的行并回上一行；顺带修复
   表内小数拆行（"0."+"1"→"0.1"）。除此之外正文逐字保留。
3. 块粒度：一章一块、一条（含附录条 A.x.y）一块；块号即条款号（规则集
   basis.quote_ref 引用格式：<file_id>.json#<条款号>）。
4. 误判守卫（防表格数值/日期示例被当成条号）：
   - 正文条号必须以当前章号开头；附录条号必须以当前附录字母开头；
   - 章号必须等于「下一个未出现的章号」（顺序递增），页脚页码不认；
   - 条号独行时标题从其后首个非标题短行回填（守卫拒绝时该行照常进正文，
     不丢行）。
5. PDF 提取的个别瑕疵（如小数被拆行）以 whitespace-stripped 口径匹配挂原文
   （tests/test_blocks.py 按此核对关键数值条款）。

用法：PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/build_blocks.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "knowledge" / "raw"
EXTRACTED_DIR = RAW_DIR / "_extracted"
BLOCKS_DIR = REPO_ROOT / "data" / "knowledge" / "blocks"

STANDARDS = [
    {"file_id": "gb7718-2011", "standard": "GB 7718-2011",
     "title": "食品安全国家标准 预包装食品标签通则",
     "published": "2011-04-20", "effective": "2012-04-20"},
    {"file_id": "gb7718-2025", "standard": "GB 7718-2025",
     "title": "食品安全国家标准 预包装食品标签通则",
     "published": "2025-03-16", "effective": "2027-03-16"},
    {"file_id": "gb28050-2011", "standard": "GB 28050-2011",
     "title": "食品安全国家标准 预包装食品营养标签通则",
     "published": "2011-10-12", "effective": "2013-01-01"},
    {"file_id": "gb28050-2025", "standard": "GB 28050-2025",
     "title": "食品安全国家标准 预包装食品营养标签通则",
     "published": "2025-03-16", "effective": "2027-03-16"},
]

PAGE_MARK_RE = re.compile(r"^=== PAGE (\d+) ===$")
_GB_HEADER_RE = re.compile(r"^GB\s*\d{4,5}\s*—\s*\d{4}\s*$")
_PAGE_FOOTER_RE = re.compile(r"^\d{1,3}$")
# 附录中「表X.Y …」表格标题行：把表格正文归位到语义条款块（表C.1 → 块C.1）
_TABLE_TITLE_RE = re.compile(r"^表([A-E])\.(\d+)")
# 「可选≤等前缀/附录字母 + 数字点串 + 句点」结尾的行 + 数字开头行 → 并回
# （修条号拆行："4."+"2."+"1 应在…"→"4.2.1 应在…"；附录 "A."+"2."+"1 …"；
#   顺带修复表内小数拆行 "0."+"1"→"0.1"、"≤0."+"5g"→"≤0.5g"）
_DOT_NUM_RE = re.compile(r"^(?:[A-E]|[^\d]{0,3}[\d.]*\d[\d.]*)\.$")
_DIGIT_START_RE = re.compile(r"^\d")
_CHAPTER_RE = re.compile(r"^(\d{1,2})(?:\s+(.*))?$")
_CLAUSE_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,5})\s*(.*)$")
_APPENDIX_RE = re.compile(r"^附\s*录\s*([A-Z])\s*$")
_APP_CLAUSE_RE = re.compile(r"^([A-Z])\.(\d{1,2}(?:\.\d{1,2}){0,4})\s*(.*)$")


def _iter_clean_lines(text: str):
    """产出 (page_no, line)：跳过分页标记/GB 页眉/紧跟页眉的孤立页码。

    页脚页码（紧跟 GB 页眉的 1–3 位数字或罗马数字）必须在此过滤——它不能
    交给切分器，否则与「章号独行」形态无法区分；其余孤立数字（表内单元格）
    交由切分器的章号顺序守卫兜底。
    """
    page = 0
    prev_was_header = False
    for raw in text.split("\n"):
        s = raw.strip()
        pm = PAGE_MARK_RE.match(s)
        if pm:
            page = int(pm.group(1))
            prev_was_header = False
            continue
        if not s:
            continue
        if _GB_HEADER_RE.match(s):
            prev_was_header = True
            continue
        if prev_was_header and (
            _PAGE_FOOTER_RE.match(s) or re.fullmatch(r"[IVXLCⅠⅡⅢⅣⅤ]+", s)
        ):
            prev_was_header = False
            continue
        prev_was_header = False
        yield page, s


def _normalize(pairs):
    """并回被 PDF 拆行的条号/小数；页码取被并行的页码。"""
    out: List[List] = []  # [page, line]
    for page, line in pairs:
        if out and _DOT_NUM_RE.match(out[-1][1]) and _DIGIT_START_RE.match(line):
            out[-1][1] = out[-1][1] + line
        else:
            out.append([page, line])
    return out


class _Splitter:
    """单遍切分：章/条/附录条开块，其余行进当前块；条号独行向下一行借标题。"""

    def __init__(self) -> None:
        self.blocks: List[Dict] = []
        self.cur: Optional[Dict] = None
        self.pending_title = False  # cur 刚以无标题条号开块，下一短行借作标题
        self.chapter = 0            # 已出现的最大章号（章号必须顺序递增）
        self.appendix: Optional[str] = None
        self.page = 0

    def _open(self, clause: str, title: str) -> None:
        self._close()
        self.cur = {"block_id": clause, "clause": clause, "title": title,
                    "text_lines": [], "page": self.page}
        self.blocks.append(self.cur)

    def _close(self) -> None:
        self.cur = None
        self.pending_title = False

    def _attach(self, block: Dict, line: str) -> None:
        """把行追加到既有块（附录表格归位用）：块在 finalize 时统一合并正文。"""
        self._close()
        self.cur = block
        block["text_lines"].append(line)

    def _is_heading(self, line: str) -> bool:
        return bool(_CLAUSE_RE.match(line) or _APP_CLAUSE_RE.match(line)
                    or _APPENDIX_RE.match(line) or _CHAPTER_RE.match(line))

    def feed(self, page: int, line: str) -> None:
        self.page = page

        # 条号独行后的标题回填：短行且不是任何标题形态
        if self.pending_title:
            if len(line) <= 30 and not self._is_heading(line):
                self.cur["title"] = line
                self.pending_title = False
                return
            self.pending_title = False  # 下一行不是标题 → 照常处理（不丢行）

        am = _APPENDIX_RE.match(line)
        if am:
            self.appendix = am.group(1)
            self._open(f"附录{self.appendix}", f"附录{self.appendix}")
            return

        am2 = _APP_CLAUSE_RE.match(line)
        if am2 and self.appendix is not None and am2.group(1) == self.appendix:
            clause = f"{am2.group(1)}.{am2.group(2)}"
            self._open(clause, am2.group(3))
            self.pending_title = am2.group(3) == ""
            return

        # 附录表格标题行（表C.1 …）：表格正文归属语义条款块（避免全落进最后一个条）
        tm = _TABLE_TITLE_RE.match(line)
        if tm and self.appendix is not None and tm.group(1) == self.appendix:
            target = f"{tm.group(1)}.{tm.group(2)}"
            for b in self.blocks:
                if b["clause"] == target:
                    self._attach(b, line)
                    return
            # 目标条款块不存在 → 照常落当前块

        chm = _CHAPTER_RE.match(line)
        if chm and self.appendix is None and int(chm.group(1)) == self.chapter + 1:
            self.chapter = int(chm.group(1))
            self._open(chm.group(1), chm.group(2) or "")
            self.pending_title = chm.group(2) is None
            return

        cm = _CLAUSE_RE.match(line)
        if cm and self.appendix is None and self.chapter > 0 \
                and int(cm.group(1).split(".")[0]) == self.chapter:
            self._open(cm.group(1), cm.group(2))
            self.pending_title = cm.group(2) == ""
            return

        if self.cur is None:
            self._open("前言", "")
        self.cur["text_lines"].append(line)

    def finalize(self) -> List[Dict]:
        self._close()
        for b in self.blocks:
            b["text"] = "\n".join(b.pop("text_lines")).strip()
        return self.blocks


def _chapter_of(blocks: List[Dict], index: int) -> str:
    """块的所属章/附录（向上找最近的章/附录块标题）。"""
    for j in range(index, -1, -1):
        clause = blocks[j]["clause"]
        if clause.startswith("附录"):
            return blocks[j]["title"] or clause
        if clause.isdigit():
            return blocks[j]["title"] or clause
    return ""


def build_one(meta: Dict[str, str]) -> Path:
    txt_path = EXTRACTED_DIR / f"{meta['file_id']}.txt"
    pdf_path = RAW_DIR / f"{meta['file_id']}.pdf"
    text = txt_path.read_text(encoding="utf-8")

    sp = _Splitter()
    for page, line in _normalize(_iter_clean_lines(text)):
        sp.feed(page, line)
    blocks = sp.finalize()

    for idx, b in enumerate(blocks):
        b["chapter"] = _chapter_of(blocks, idx)
        b["appendix"] = b["clause"].startswith("附录") or bool(re.match(r"^[A-Z]\.", b["clause"]))

    doc = {
        "file_id": meta["file_id"],
        "standard": meta["standard"],
        "title": meta["title"],
        "published": meta["published"],
        "effective": meta["effective"],
        "source_pdf": pdf_path.relative_to(REPO_ROOT).as_posix(),
        "source_pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "extracted_text": txt_path.relative_to(REPO_ROOT).as_posix(),
        "extraction_tool": "PyMuPDF get_text('text')，重提取命令见 tools/build_blocks.py 模块注释",
        "status_note": "条文块由官方 PDF 提取文本切分（M3，2026-10-04）；块号=条款号，"
        "正文逐字保留（PDF 拆行的小数按去空白口径匹配）。标准文本版权归发布机构，仅供学习研究。",
        "block_count": len(blocks),
        "blocks": blocks,
    }
    BLOCKS_DIR.mkdir(parents=True, exist_ok=True)
    out = BLOCKS_DIR / f"{meta['file_id']}.json"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return out


def main() -> None:
    for meta in STANDARDS:
        out = build_one(meta)
        n = json.loads(out.read_text(encoding="utf-8"))["block_count"]
        print(f"[build_blocks] {meta['file_id']}: {n} blocks -> "
              f"{out.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
