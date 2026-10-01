"""원문 접속(매체 확인)에 실패한 기사를 제외한다.

실패 기준: source_lookup.csv에서 원문 URL 변환 오류가 있거나 원문 응답 코드가 200이 아님
입력: data/processed/google_news_ev_source_fixed.csv, data/processed/source_lookup.csv
출력: data/processed/google_news_ev_final.csv
      outputs/tables/lookup_failed_removed.csv
"""
from pathlib import Path

import pandas as pd

SRC = Path("data/processed/google_news_ev_source_fixed.csv")
LOOKUP = Path("data/processed/source_lookup.csv")
OUT = Path("data/processed/google_news_ev_final.csv")
TABLE = Path("outputs/tables/lookup_failed_removed.csv")

df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
lk = pd.read_csv(LOOKUP, dtype=str, keep_default_na=False)

status = pd.to_numeric(lk["http_status"], errors="coerce")
failed = lk[(lk["error"] != "") | (status != 200)]
mask = df["link"].isin(failed["link"])

removed = df[mask].merge(failed[["link", "article_url", "http_status", "error"]], on="link")
removed.to_csv(TABLE, index=False, encoding="utf-8-sig")
print(f"입력 {len(df)}건, 원문 접속 실패 제외 {mask.sum()}건")
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(removed[["lang", "source", "http_status", "title", "published_at"]].to_string())

df = df[~mask]
df.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"\n최종 {len(df)}건, 언어별 {df['lang'].value_counts().to_dict()}")
print(f"저장: {OUT}")
