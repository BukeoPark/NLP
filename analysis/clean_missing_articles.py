"""제목·링크가 없거나 발행일을 해석할 수 없는 기사를 제외한다.

입력: data/raw/google_news_ev_*.csv 중 가장 최근 파일
출력: data/processed/google_news_ev_clean.csv
"""
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
OUT = Path("data/processed/google_news_ev_clean.csv")

src = sorted(RAW_DIR.glob("google_news_ev_*.csv"))[-1]
df = pd.read_csv(src, dtype=str, keep_default_na=False)
print(f"입력: {src} ({len(df)}건)")

# 공백만 있는 값도 없는 것으로 본다
title_missing = df["title"].str.strip().eq("")
link_missing = df["link"].str.strip().eq("")
published = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
date_missing = published.isna()

reasons = pd.DataFrame({
    "제목 없음": title_missing,
    "링크 없음": link_missing,
    "발행일 없음/해석 불가": date_missing,
})
print("\n제외 기준별 건수 (중복 해당 가능)")
print(reasons.sum().to_string())

excluded = reasons.any(axis=1)
print(f"\n제외 {excluded.sum()}건, 유지 {(~excluded).sum()}건")
print("언어별 유지 건수:", df.loc[~excluded, "lang"].value_counts().to_dict())

if excluded.any():
    shown = df[excluded].copy()
    shown["제외사유"] = reasons[excluded].apply(
        lambda r: ", ".join(r.index[r]), axis=1)
    print("\n제외된 기사")
    print(shown.to_string())

OUT.parent.mkdir(parents=True, exist_ok=True)
df[~excluded].to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"\n저장: {OUT}")
