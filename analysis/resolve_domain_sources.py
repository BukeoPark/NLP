"""매체 열 표기를 정리한다.

1) 조선비즈 표기 통일: Chosunbiz → 조선비즈
2) 매체 열에 도메인이 들어간 기사는 원문에 접속해 매체명을 확인하고 채운다.
   - Google 뉴스 링크를 원문 URL로 변환 → 원문 페이지의 메타 태그에서 매체명 후보 추출
   - 조회 결과는 data/processed/source_lookup.csv에 저장하고, 파일이 있으면 재사용한다
     (원문 페이지가 바뀌거나 사라져도 같은 결과를 재현하기 위함, 다시 조회하려면 --refresh)
   - 조회 결과를 검토해 DOMAIN_SOURCE에 매체명과 근거를 확정한다

입력: data/processed/google_news_ev_dedup.csv
출력: data/processed/google_news_ev_source_fixed.csv
      data/processed/source_lookup.csv          (원문 URL·메타 조회 결과)
      outputs/tables/source_replaced.csv        (매체명 변경 내역)
"""
import html
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

SRC = Path("data/processed/google_news_ev_dedup.csv")
OUT = Path("data/processed/google_news_ev_source_fixed.csv")
LOOKUP = Path("data/processed/source_lookup.csv")
TABLE = Path("outputs/tables/source_replaced.csv")
H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

SOURCE_RENAME = {"Chosunbiz": "조선비즈"}
# 도메인 형태 매체값: 영문 소문자 도메인 또는 대소문자 섞인 "이름.com" 형태
# (Google이 기관명 뒤에 붙인 "(.gov)" 표기는 기관명이 이미 있으므로 대상에서 제외)
DOMAIN_RE = r"^(?!.*\(\.gov\))[\w\-]+(?:\.[\w\-]+)*\.(?:com|net|org|kr|tv|gov|io)$"
# 원문 조회 결과(source_lookup.csv)를 검토해 확정한 매체명: 도메인 매체값 -> (매체명, 근거)
# v.daum.net은 포털이므로 기사별로 원문의 article:media_name(제공 언론사)을 사용한다
DOMAIN_SOURCE = {
    "newstree.kr": ("뉴스트리", "원문 og:site_name '뉴스;트리(주)'(법인명) → 제호"),
    "news.einfomax.co.kr": ("연합인포맥스", "원문 og:site_name"),
    "theguru.co.kr": ("더구루", "홈페이지 title"),
    "zdnet.co.kr": ("지디넷코리아", "원문 title 'ZDNet korea', 홈페이지 title"),
    "vcreporter.com": ("VC Reporter", "원문 429 → 홈페이지 og:site_name"),
    "markets.businessinsider.com": ("Markets Insider", "원문 title"),
    "kasu.org": ("KASU", "원문 og:site_name"),
    "nbcchicago.com": ("NBC Chicago", "원문 og:site_name"),
    "techxplore.com": ("Tech Xplore", "원문 403 → 홈페이지 og:site_name"),
    "MLive.com": ("MLive", "원문·홈페이지 403 → 공식 명칭"),
    "columbiaspectator.com": ("Columbia Daily Spectator", "원문 og:site_name"),
    "thecentersquare.com": ("The Center Square", "원문 og:site_name"),
    "cbs19.tv": ("CBS19", "원문 403 → 홈페이지 title"),
    "thetruthaboutcars.com": ("The Truth About Cars", "원문 title"),
    "vtcng.com": ("Vermont Community Newspaper Group", "원문 429 → 홈페이지 og:site_name"),
    "Motor1.com": ("Motor1.com", "원문 og:site_name (도메인이 공식 명칭, 유지)"),
    "NYC.gov": ("City of New York", "원문 title"),
    "CBS17.com": ("CBS 17", "원문·홈페이지 403 → 공식 명칭"),
    "fox43.com": ("FOX43", "원문 403 → 홈페이지 title 'WPMT FOX43'"),
    "EVChargingStations.com": ("EVChargingStations.com", "원문 og:site_name은 부제 포함 문구 → 도메인이 공식 명칭, 유지"),
    "wsj.com": ("The Wall Street Journal", "원문 401(유료) → 공식 명칭"),
    "Euronews.com": ("Euronews", "원문 title"),
    "CarNewsChina.com": ("CarNewsChina.com", "원문 og:site_name (도메인이 공식 명칭, 유지)"),
}
PORTAL = {"v.daum.net"}


def decode_google_link(link):
    aid = link.split("/articles/")[1].split("?")[0]
    r = requests.get(f"https://news.google.com/rss/articles/{aid}", headers=H, timeout=20)
    sg = re.search(r'data-n-a-sg="([^"]+)"', r.text).group(1)
    ts = re.search(r'data-n-a-ts="([^"]+)"', r.text).group(1)
    req = [[["Fbv4je",
             f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,'
             f'null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{aid}",{ts},"{sg}"]',
             None, "generic"]]]
    p = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                      data={"f.req": json.dumps(req)}, timeout=20,
                      headers={**H, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    body = json.loads(p.text.split("\n\n")[1])[:-2]
    return json.loads(body[0][2])[1]


def meta(text, *names):
    for n in names:
        m = (re.search(rf'<meta[^>]+(?:property|name)=["\']{n}["\'][^>]*content=["\']([^"\']+)', text, re.I)
             or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{n}["\']', text, re.I))
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def lookup(link):
    row = {"link": link, "article_url": "", "http_status": "", "og_site_name": "",
           "media_name": "", "author": "", "page_title": "", "error": ""}
    try:
        url = decode_google_link(link)
        row["article_url"] = url
        r = requests.get(url, headers=H, timeout=20)
        r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
        t = r.text
        row["http_status"] = r.status_code
        row["og_site_name"] = meta(t, "og:site_name")
        row["media_name"] = meta(t, "article:media_name", "og:article:author")
        row["author"] = meta(t, "author")
        m = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
        row["page_title"] = html.unescape(m.group(1)).strip() if m else ""
    except Exception as e:  # 접속 실패도 기록하고 다음 기사로 진행
        row["error"] = f"{type(e).__name__}: {e}"[:200]
    return row


df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
orig_source = df["source"].copy()

# 1) 표기 통일
df["source"] = df["source"].replace(SOURCE_RENAME)
print(f"[1] 표기 통일: {(orig_source != df['source']).sum()}건 {SOURCE_RENAME}")

# 2) 도메인 매체값 조회
target = df["source"].str.match(DOMAIN_RE)
print(f"[2] 도메인 형태 매체값: {target.sum()}건, {df.loc[target, 'source'].nunique()}종")

cache = pd.read_csv(LOOKUP, dtype=str, keep_default_na=False) if LOOKUP.exists() and "--refresh" not in sys.argv else pd.DataFrame(columns=["link"])
todo = [l for l in df.loc[target, "link"] if l not in set(cache["link"])]
rows = []
for i, l in enumerate(todo, 1):
    rows.append(lookup(l))
    print(f"  조회 {i}/{len(todo)}", rows[-1]["article_url"][:70], rows[-1]["error"][:60])
    time.sleep(1)
cache = pd.concat([cache, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("link", keep="last")
LOOKUP.parent.mkdir(parents=True, exist_ok=True)
cache.to_csv(LOOKUP, index=False, encoding="utf-8-sig")

info = df.loc[target, ["lang", "source", "link"]].merge(cache, on="link", how="left")
info.index = df.index[target]
portal = info["source"].isin(PORTAL)
info["new_source"] = info["source"].map(lambda x: DOMAIN_SOURCE.get(x, ("", ""))[0])
info["evidence"] = info["source"].map(lambda x: DOMAIN_SOURCE.get(x, ("", ""))[1])
info.loc[portal, "new_source"] = info.loc[portal, "media_name"]
info.loc[portal, "evidence"] = "포털 원문 article:media_name"
unresolved = info["new_source"].eq("")
if unresolved.any():
    print("매체명을 확정하지 못한 도메인 (DOMAIN_SOURCE에 추가 필요):")
    print(info.loc[unresolved, ["source", "article_url"]].to_string())
    sys.exit(1)

df.loc[info.index, "source"] = info["new_source"]

log = pd.DataFrame({"lang": df["lang"], "title": df["title"], "source_before": orig_source,
                    "source_after": df["source"]})
log["reason"] = ""
log.loc[orig_source.isin(SOURCE_RENAME), "reason"] = "표기 통일"
log.loc[info.index, "reason"] = "도메인 → 원문 확인: " + info["evidence"]
log["article_url"] = ""
log.loc[info.index, "article_url"] = info["article_url"]
log = log[log["reason"] != ""]
log.to_csv(TABLE, index=False, encoding="utf-8-sig")
changed = log["source_before"] != log["source_after"]
print(f"\n매체명 변경 {changed.sum()}건 (대상 {len(log)}건 중, 나머지는 기존 값 유지)")
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 50)
print(log[["source_before", "source_after", "reason"]].drop_duplicates().to_string(index=False))

# 매체명 변경으로 새로 생긴 제목+매체 중복 (이번 단계에서는 제외하지 않고 알림)
dup = df[df.duplicated(["title", "source"], keep=False)]
if len(dup):
    print(f"\n[참고] 매체명 변경 후 제목+매체가 같아진 기사 {len(dup)}건")
    print(dup[["lang", "title", "source", "published_at"]].to_string())

df.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"\n최종 {len(df)}건, 저장: {OUT}")
