#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

DEGREE_WORDS = ["博士", "硕士", "本科", "大专", "中专", "高中"]
FULLTIME_WORDS = [(r"全日制", "全日制"), (r"非全日制|成人教育|自考|函授", "非全日制")]
STOP_LABELS = ["意向城市", "期望薪资", "电话", "邮箱", "性别", "年龄", "现所在地", "最高学历", "籍贯", "政治面貌"]
SENDER_NAME_BLOCKLIST = {"许建锋"}
NAME_SUFFIX_BLACKLIST = ("简历", "个人简历", "候选人", "应聘", "求职")
TITLE_HINT_WORDS = (
    "经理",
    "工程师",
    "主管",
    "专员",
    "助理",
    "总监",
    "开发",
    "设计",
    "销售",
    "采购",
    "运营",
    "产品",
    "结构",
    "软件",
    "硬件",
    "项目",
    "客服",
    "人事",
    "行政",
    "财务",
    "会计",
    "老师",
    "顾问",
)
NAME_CONTEXT_STOPWORDS = {
    "非党员",
    "党员",
    "团员",
    "群众",
    "干部",
    "项目经理",
    "产品经理",
    "销售工程师",
    "软件工程师",
    "结构工程师",
    "采购工程师",
    "解决方案经理",
}
NON_NAME_WORDS = {
    *DEGREE_WORDS,
    *NAME_CONTEXT_STOPWORDS,
    "采购",
    "工程师",
    "简历",
    "姓名",
    "联系方式",
    "自动化",
}
NAME_PREFIX_BLACKLIST = (
    "熟练",
    "熟悉",
    "掌握",
    "了解",
    "负责",
    "从事",
    "深圳",
    "广州",
    "上海",
    "北京",
    "武汉",
    "成都",
    "苏州",
    "杭州",
    "东莞",
    "佛山",
    "南京",
    "重庆",
    "天津",
    "西安",
    "厦门",
    "长沙",
    "郑州",
    "青岛",
    "宁波",
)


def compact_resume_text(text: str) -> str:
    text = (text or "").replace("\u3000", " ")
    text = re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fa5])\s*(?=[:：])", "", text)
    text = re.sub(r"(?<=[:：])\s*(?=[\u4e00-\u9fa5A-Za-z0-9])", "", text)
    text = re.sub(r"(?<=\d)\s+(?=岁)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def dense_resume_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def normalize_candidate_name(name: str) -> str:
    name = re.sub(r"\s+", "", name or "")
    name = re.sub(r"(?:简历|个人简历|候选人|应聘)$", "", name)
    mixed = re.match(r"^([\u4e00-\u9fa5]{2,4})[A-Za-z][A-Za-z0-9._-]*$", name)
    if mixed:
        name = mixed.group(1)
    if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
        return ""
    if name in SENDER_NAME_BLOCKLIST or name in NON_NAME_WORDS:
        return ""
    if any(suffix in name for suffix in NAME_SUFFIX_BLACKLIST):
        return ""
    if any(word in name for word in TITLE_HINT_WORDS):
        return ""
    if any(name.startswith(prefix) for prefix in NAME_PREFIX_BLACKLIST):
        return ""
    if name.endswith(("公司", "科技", "学院", "大学", "城市")):
        return ""
    return name


def pick_name(text: str) -> str:
    normalized = compact_resume_text(text)
    dense = dense_resume_text(text)
    m = re.search(r"姓名[:：]?([\u4e00-\u9fa5\sA-Za-z]{2,20}?)(?=\s*(?:年龄|性别|电话|邮箱|出生|生日|求职意向|应聘岗位|现居住地|现所在地|籍贯|$))", normalized)
    if m:
        picked = normalize_candidate_name(m.group(1))
        if picked:
            return picked
    m = re.search(r"姓名[:：]?([\u4e00-\u9fa5]{2,4})(?=(?:年龄|性别|电话|邮箱|出生|生日|求职意向|应聘岗位|现居住地|现所在地|籍贯|$))", dense)
    if m:
        picked = normalize_candidate_name(m.group(1))
        if picked:
            return picked
    patterns = [
        r"(?:^|[|｜\s])([\u4e00-\u9fa5]{2,4})(?=\s*(?:[|｜]\s*)?1[3-9]\d{9})",
        r"(?:^|[|｜\s])([\u4e00-\u9fa5]{2,4})(?=\s*(?:[|｜]\s*)?\d+年工作经验)",
        r"(?:^|[|｜\s])([\u4e00-\u9fa5]{2,4})(?=\s*(?:[|｜]\s*)?[男女A-Za-z])",
        r"(?:^|[|｜\s])([\u4e00-\u9fa5]{2,4})(?=\s*(?:[|｜]\s*)?(?:求职意向|期望薪资|期望城市|年龄|籍贯))",
    ]
    for variant in (normalized, dense):
        for pat in patterns:
            m = re.search(pat, variant)
            if m:
                picked = normalize_candidate_name(m.group(1))
                if picked:
                    return picked
    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    normalized_lines = [re.sub(r"\s+", "", ln) for ln in raw_lines]
    for i, ln in enumerate(normalized_lines[:6]):
        if ln in NAME_CONTEXT_STOPWORDS:
            continue
        if any(word in ln for word in TITLE_HINT_WORDS):
            continue
        next_line = normalized_lines[i + 1] if i + 1 < len(normalized_lines) else ""
        if re.search(r"(?:1[3-9]\d{9}|年龄|岁|求职意向|应聘岗位|邮箱|@)", next_line):
            picked = normalize_candidate_name(ln)
            if picked:
                return picked
    return ""


def pick_name_from_filename(pdf_path: str | None) -> str:
    if not pdf_path:
        return ""
    stem = Path(pdf_path).stem
    stem = re.sub(r"^\[[^\]]+\]\s*", "", stem)
    stem = re.sub(r"^【[^】]+】\s*", "", stem)
    stem = re.sub(r"(?:简历|个人简历|候选人简历|应聘简历)", " ", stem)
    stem = re.sub(r"[（(【\[][^）)】\]]+[）)】\]]", " ", stem)
    stem = re.sub(r"[_\-\s]+", " ", stem).strip()
    candidates: list[str] = []
    for part in re.split(r"\s+", stem):
        if part:
            candidates.append(part)
    candidates.extend(re.findall(r"[\u4e00-\u9fa5]{2,6}", stem))
    for cand in candidates:
        picked = normalize_candidate_name(cand)
        if picked:
            return picked
    return ""


def pick_phone(text: str) -> str:
    m = re.search(r"(?<!\d)(1[3-9]\d{9})(?!\d)", text)
    return m.group(1) if m else ""


def pick_email(text: str) -> str:
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return m.group(0) if m else ""


def pick_contact(text: str) -> str:
    phone = pick_phone(text)
    email = pick_email(text)
    if phone and email:
        return f"{phone} / {email}"
    return phone or email or ""


def pick_age(text: str) -> str:
    normalized = compact_resume_text(text)
    dense = dense_resume_text(text)
    for variant in (normalized, dense):
        m = re.search(r"年龄\s*[:：]?\s*(\d{2})", variant)
        if m:
            return m.group(1)
        m = re.search(r"年龄\s*[:：]?\s*(\d)\s*(\d)", variant)
        if m:
            return f"{m.group(1)}{m.group(2)}"
        m = re.search(r"(?<!\d)(\d{2})\s*岁(?!\d)", variant)
        if m:
            return m.group(1)
        m = re.search(r"(?<!\d)(\d)\s*(\d)\s*岁(?!\d)", variant)
        if m:
            return f"{m.group(1)}{m.group(2)}"
        m = re.search(r"(?:出生年月|出生日期|生日|出生)\s*[:：]?\s*(\d{4})[年./-]?(\d{1,2})(?:[月./-]?(\d{1,2}))?", variant)
        if m:
            birth_year = int(m.group(1))
            birth_month = int(m.group(2))
            birth_day = int(m.group(3) or 1)
            today = date.today()
            age = today.year - birth_year - ((today.month, today.day) < (birth_month, birth_day))
            if 16 <= age <= 80:
                return str(age)
    return ""


def pick_degree(text: str) -> str:
    for word in DEGREE_WORDS:
        if word in text:
            return word
    return ""


def pick_school(text: str) -> str:
    m = re.search(r"([\u4e00-\u9fa5A-Za-z（）()·]{2,40}(大学|学院))", text)
    return m.group(1) if m else ""


def clean_major_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" ：:;；，,。")
    value = re.split(r"(?:主修课程|课程|工作经历|项目经历|教育背景|个人技能|荣誉奖项|校园经历|内容[:：]|业绩[:：]|公司[:：]|岗位[:：]|时间[:：]|联系方式[:：]|电话[:：]|邮箱[:：])", value)[0].strip(" ：:;；，,。")
    if not value:
        return ""
    if re.fullmatch(r"\d{4}(?:[./-]\d{1,2})?(?:\s*[-~至到]\s*\d{4}(?:[./-]\d{1,2})?)?", value):
        return ""
    if re.search(r"\d{4}\s*[-~至到]\s*\d{4}", value):
        return ""
    if re.search(r"主修课程", value):
        return ""
    school_prefix = re.match(r"^([\u4e00-\u9fa5A-Za-z（）()·]{2,20}(?:大学|学院))(.*专业)$", value)
    if school_prefix:
        value = school_prefix.group(2).strip()
    value = re.sub(r"^(?:博士|硕士|本科|大专|中专|高中)", "", value).strip()
    if len(value) > 20:
        return ""
    return value


def pick_major(text: str) -> str:
    compact = compact_resume_text(text)

    patterns = [
        r"(?:专业|所学专业|就读专业)[:：]\s*([^\n|｜]{2,30})",
        r"(?:大学|学院|学校)\s*([\u4e00-\u9fa5A-Za-z/＋+（）()·]{2,20}专业)(?=\s|\d|$)",
        r"([\u4e00-\u9fa5A-Za-z/＋+（）()·]{2,20}专业)(?=\s*(?:\d{4}|主修课程|$))",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, compact):
            raw = match.group(1).strip()
            cleaned = clean_major_value(raw)
            if cleaned:
                return cleaned
    return ""


def pick_fulltime(text: str) -> str:
    for pat, val in FULLTIME_WORDS:
        if re.search(pat, text):
            return val
    return ""


def pick_latest_company(text: str) -> str:
    m = re.search(r"(?:最近一家公司|最近公司|现公司|就职于)[:：\s]+([^\n]{2,40})", text)
    if m:
        return m.group(1).strip()
    compact = re.sub(r"\s+", " ", text)
    m = re.search(r"([\u4e00-\u9fa5A-Za-z（）()·]{2,40}(?:有限公司|股份有限公司))\s+(?:C/C\+\+开发工程师|采购专员|采购工程师|项目经理|软件工程师)", compact)
    return m.group(1).strip() if m else ""


def pick_salary(text: str, label: str) -> str:
    m = re.search(label + r"[:：\s]+(.+)", text)
    if not m:
        return ""
    value = m.group(1)
    stop_positions = [value.find(tok) for tok in STOP_LABELS if tok in value]
    stop_positions = [p for p in stop_positions if p >= 0]
    if stop_positions:
        value = value[: min(stop_positions)]
    value = re.split(r"[\n\r|｜]", value)[0].strip().strip(" ：:;；，,")
    if any(tok in value for tok in ["面议", "保密", "详谈"]):
        return ""
    if re.search(r"\d", value):
        return value
    return ""


def pick_position(text: str) -> str:
    m = re.search(r"(?:应聘岗位|求职意向|意向岗位|面试岗位)[:：\s]+(.+)", text)
    if not m:
        return ""
    value = m.group(1)
    stop_positions = [value.find(label) for label in STOP_LABELS if label in value]
    stop_positions = [p for p in stop_positions if p >= 0]
    if stop_positions:
        value = value[: min(stop_positions)]
    value = re.split(r"[\n\r|｜]", value)[0].strip()
    value = re.sub(r"\s{2,}", " ", value).strip(" ：:;；，,|｜")
    return value


def build_fields(text: str, pdf_path: str | None = None) -> dict[str, str]:
    candidate_name = pick_name(text)
    if not candidate_name:
        candidate_name = pick_name_from_filename(pdf_path)
    fields = {
        "应聘者姓名": candidate_name,
        "年龄": pick_age(text),
        "应聘岗位": pick_position(text),
        "联系方式": pick_contact(text),
        "学历": pick_degree(text),
        "毕业院校": pick_school(text),
        "专业": pick_major(text),
        "是否为全日制": pick_fulltime(text),
        "最近一家公司名称": pick_latest_company(text),
        "目前薪资": pick_salary(text, "目前薪资"),
        "期望薪资": pick_salary(text, "期望薪资"),
    }
    fields = {k: v for k, v in fields.items() if v not in ("", None)}
    if fields.get("应聘者姓名") in SENDER_NAME_BLOCKLIST:
        fields.pop("应聘者姓名", None)
    return fields


def main() -> int:
    ap = argparse.ArgumentParser(description="Build conservative candidate fields JSON from resume text")
    ap.add_argument("resume_text_path")
    ap.add_argument("output_fields_json")
    ap.add_argument("--pdf-path")
    args = ap.parse_args()

    src = Path(args.resume_text_path)
    dst = Path(args.output_fields_json)
    text = src.read_text(encoding="utf-8", errors="ignore")
    fields = build_fields(text, pdf_path=args.pdf_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(fields, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
