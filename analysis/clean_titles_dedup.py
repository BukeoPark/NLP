"""제목 정리(HTML 문자·공백, 끝에 붙은 매체명) 후 제목+매체가 같은 중복 기사를 제외한다.

입력: data/processed/google_news_ev_clean.csv
출력: data/processed/google_news_ev_dedup.csv
      outputs/tables/title_suffix_removed.csv  (매체명 제거 내역)
      outputs/tables/duplicates_removed.csv    (중복으로 제외한 기사)

참고: 수집 단계(collect_google_news_rss.py)에서 Google 뉴스가 붙인 " - <매체>"는
이미 한 번 제거되었다. 여기서는 언론사가 원래 제목에 넣어 둔 매체명을 처리한다.
"""
import html
import re
from pathlib import Path

import pandas as pd

SRC = Path("data/processed/google_news_ev_clean.csv")
OUT = Path("data/processed/google_news_ev_dedup.csv")
TABLE_DIR = Path("outputs/tables")

# 매체 열 값과 표기가 다르지만 같은 매체를 가리키는 이름 (데이터를 직접 확인해 지정)
SOURCE_ALIASES = {
    "Chosunbiz": ["조선비즈"],
    "Hyundai Motor Group": ["현대자동차그룹"],
    "WDIY": ["WDIY Local News"],
    "OurQuadCities": ["WHBF"],  # ourquadcities.com은 WHBF 방송국 사이트
}
# 제목 끝 구분자: " - ", " – ", " — ", " | "
SEP = r"\s+[-–—|]\s+"
# 매체명 앞에 붙은 사이트 섹션명 (예: "| 뉴스 | 현대자동차그룹")
SECTION = r"(?:\s+\|\s+[^|]{1,10})?"


def clean_text(s):
    s = html.unescape(html.unescape(s))           # &amp;quot; 같은 이중 인코딩 대비
    s = re.sub(r"<[^>]+>", "", s)                 # HTML 태그
    s = re.sub(r"[ ​　\s]+", " ", s)  # 특수 공백·연속 공백
    return s.strip()


def strip_source_suffix(title, source):
    names = [source] + SOURCE_ALIASES.get(source, [])
    for name in sorted(names, key=len, reverse=True):
        pat = SECTION + SEP + re.escape(name) + r"$"
        new = re.sub(pat, "", title)
        if new != title:
            return new.strip(), name
    return title, None


df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
n0 = len(df)
print(f"입력: {SRC} ({n0}건)")

# 1) HTML 문자·공백 정리
before = df["title"].copy()
df["title"] = df["title"].map(clean_text)
df["source"] = df["source"].map(clean_text)
print(f"\n[1] HTML 문자·공백 정리로 바뀐 제목: {(before != df['title']).sum()}건")

# 2) 제목 끝 매체명 제거
res = [strip_source_suffix(t, s) for t, s in zip(df["title"], df["source"])]
new_titles = pd.Series([r[0] for r in res], index=df.index)
matched = pd.Series([r[1] for r in res], index=df.index)
changed = new_titles != df["title"]
log = pd.DataFrame({
    "lang": df["lang"], "source": df["source"], "removed_name": matched,
    "match_type": ["매체 열과 일치" if m == s else "별칭" for m, s in zip(matched, df["source"])],
    "title_before": df["title"], "title_after": new_titles,
})[changed]
df["title"] = new_titles
print(f"[2] 제목 끝 매체명 제거: {changed.sum()}건")
print(log[["lang", "source", "removed_name", "match_type", "title_after"]].to_string())
log.to_csv(TABLE_DIR / "title_suffix_removed.csv", index=False, encoding="utf-8-sig")

# 남은 " - X" 형태 꼬리 중 매체명이 아닌 것 확인용
tail = df["title"].str.extract(SEP + r"([^-–—|]{1,30})$")[0]
print("\n[참고] 제거하지 않은 제목 끝 구분자 뒤 문구 (매체명 아님으로 판단)")
print(df.loc[tail.notna(), ["lang", "source"]].assign(tail=tail).to_string())

# 3) 제목+매체 완전 중복 제외 (최신 발행 기사 1건 유지)
df = df.sort_values(["lang", "published_at"], ascending=[True, False], kind="stable")
dup = df.duplicated(["title", "source"], keep="first")
df[dup].to_csv(TABLE_DIR / "duplicates_removed.csv", index=False, encoding="utf-8-sig")
print(f"\n[3] 제목+매체 중복 제외: {dup.sum()}건")
print(df.loc[df.duplicated(["title", "source"], keep=False),
             ["lang", "title", "source", "published_at"]].assign(제외=dup).to_string())
df = df[~dup]

# 매체만 다른 같은 제목 (제외하지 않음)
same_title = df[df.duplicated("title", keep=False)]
print(f"\n[참고] 제목은 같고 매체가 다른 기사 (유지): {len(same_title)}건")
print(same_title[["lang", "title", "source"]].to_string())

df = df.sort_values(["lang", "published_at"], ascending=[False, False], kind="stable")
df.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"\n최종 {len(df)}건 (입력 {n0}건 - 중복 {dup.sum()}건)")
print("언어별:", df["lang"].value_counts().to_dict())
print(f"저장: {OUT}")
