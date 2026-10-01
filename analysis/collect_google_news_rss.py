"""Google 뉴스 RSS에서 최근 30일 전기차 뉴스를 언어별로 수집한다.

출력: data/raw/google_news_ev_<수집일시>.csv
열: lang, query, title, published_at, source, link, collected_at
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

import pandas as pd
import requests

QUERIES = {
    "ko": {"q": "전기차", "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    "en": {"q": "electric vehicle", "hl": "en-US", "gl": "US", "ceid": "US:en"},
}
DAYS = 30
MAX_ITEMS = 100
OUT_DIR = Path("data/raw")


def fetch(lang, cfg, collected_at):
    url = (
        "https://news.google.com/rss/search?q="
        + quote(f"{cfg['q']} when:{DAYS}d")
        + f"&hl={cfg['hl']}&gl={cfg['gl']}&ceid={cfg['ceid']}"
    )
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    rows = []
    for item in root.iter("item"):
        source = item.findtext("source", default="")
        title = item.findtext("title", default="")
        # 제목 끝의 " - 매체명" 접미사는 매체 열과 중복이므로 제거
        suffix = f" - {source}"
        if source and title.endswith(suffix):
            title = title[: -len(suffix)]
        rows.append({
            "lang": lang,
            "query": cfg["q"],
            "title": title,
            "published_at": parsedate_to_datetime(item.findtext("pubDate")),
            "source": source,
            "link": item.findtext("link", default=""),
            "collected_at": collected_at,
        })
    df = pd.DataFrame(rows)
    n_fetched = len(df)
    # 최근 30일 범위 밖 기사 제외
    cutoff = collected_at - timedelta(days=DAYS)
    df = df[df["published_at"] >= cutoff]
    n_old = n_fetched - len(df)
    # 같은 링크 중복 제외
    n_before = len(df)
    df = df.drop_duplicates("link")
    n_dup = n_before - len(df)
    df = df.sort_values("published_at", ascending=False).head(MAX_ITEMS)
    print(f"[{lang}] RSS 항목 {n_fetched}건, 30일 이전 제외 {n_old}건, "
          f"링크 중복 제외 {n_dup}건 → 저장 {len(df)}건")
    return df


def main():
    collected_at = datetime.now(timezone.utc)
    df = pd.concat([fetch(lang, cfg, collected_at) for lang, cfg in QUERIES.items()],
                   ignore_index=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"google_news_ev_{collected_at:%Y%m%d_%H%M%S}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"저장: {out}")

    print("\n언어별 기사 수")
    print(df["lang"].value_counts().to_string())
    for lang, g in df.groupby("lang", sort=False):
        print(f"\n[{lang}] 제목 예시")
        for t in g["title"].head(3):
            print(" -", t)


if __name__ == "__main__":
    main()
