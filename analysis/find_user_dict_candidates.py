"""Kiwi 사용자 사전 후보 탐색 (기본 사전 기준).

어절에서 조사·어미 앞의 체언 덩어리가 여러 형태소로 쪼개지거나,
외국어/숫자와 조사가 잘못 결합된 경우를 모아 빈도순으로 저장한다.
최종 등록 여부는 사람이 검토해 tokenize_titles.py의 USER_WORDS에 반영한다.

입력: data/processed/google_news_ev_final.csv
출력: outputs/tables/user_dict_candidates.csv
"""
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from kiwipiepy import Kiwi

SRC = Path("data/processed/google_news_ev_final.csv")
OUT = Path("outputs/tables/user_dict_candidates.csv")
HEAD_TAGS = {"NNG", "NNP", "SL", "SN", "XSN", "NR", "XPN", "SH"}

df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
titles = df.loc[df["lang"] == "ko", "title"].tolist()
kiwi = Kiwi()

cnt, analysis = Counter(), {}
for title in titles:
    for w in re.findall(r"[0-9A-Za-z가-힣]+", title):
        toks = kiwi.tokenize(w)
        head = []
        for t in toks:
            if t.tag not in HEAD_TAGS:
                break
            head.append(t)
        if len(head) >= 2:
            key = "".join(t.form for t in head)
        elif toks and toks[0].tag == "SL" and len(toks) > 1 and toks[1].tag.startswith("J"):
            key = w  # 예: LG엔솔 → LG/SL 에/JKB ...
            head = toks
        else:
            continue
        cnt[key] += 1
        analysis[key] = " ".join(f"{t.form}/{t.tag}" for t in head)

out = pd.DataFrame([(k, v, analysis[k]) for k, v in cnt.most_common()],
                   columns=["candidate", "freq", "kiwi_default"])
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"후보 {len(out)}개 저장: {OUT}")
print(out.head(40).to_string(index=False))
