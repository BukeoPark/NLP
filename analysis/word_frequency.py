"""언어별 자주 나온 단어 상위 20개.

- 한국어: 형태소 중 명사(NNG 일반명사, NNP 고유명사)만 사용
- 영어: scikit-learn 영어 불용어(318개) 제외, 숫자만으로 된 토큰 제외,
        소유격 's·’s는 떼고 집계 (ev's → ev)
- 기사 수: 단어가 한 번 이상 나온 기사 수 / 총 등장 횟수: 전체 출현 횟수
- 정렬: 기사 수 → 총 등장 횟수 → 단어 순

입력: data/processed/google_news_ev_tokens.csv (동의어 변환·토큰화 결과)
출력: outputs/tables/top_words_ko.csv, outputs/tables/top_words_en.csv
"""
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

SRC = Path("data/processed/google_news_ev_tokens.csv")
OUT_DIR = Path("outputs/tables")
TOP_N = 20
KO_NOUN_TAGS = {"NNG", "NNP"}


def ko_words(tokens):
    out = []
    for t in tokens.split():
        form, tag = t.rsplit("/", 1)
        if tag in KO_NOUN_TAGS:
            out.append(form)
    return out


def en_words(tokens):
    out = []
    for w in tokens.split():
        w = re.sub(r"['’]s$", "", w)
        if w in ENGLISH_STOP_WORDS or re.fullmatch(r"[\d.,\-]+", w):
            continue
        out.append(w)
    return out


df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
for lang, extract in [("ko", ko_words), ("en", en_words)]:
    words = df.loc[df["lang"] == lang, "tokens"].map(extract)
    total = Counter(w for ws in words for w in ws)
    docs = Counter(w for ws in words for w in set(ws))
    table = pd.DataFrame({"word": list(total), "article_count": [docs[w] for w in total],
                          "total_count": [total[w] for w in total]})
    table["article_share"] = table["article_count"] / len(words)
    table = table.sort_values(["article_count", "total_count", "word"],
                              ascending=[False, False, True], ignore_index=True)
    table.index += 1
    table.to_csv(OUT_DIR / f"top_words_{lang}.csv", index_label="rank", encoding="utf-8-sig")
    print(f"\n=== {lang}: 기사 {len(words)}건, 고유 단어 {len(table)}개 ===")
    show = table.head(TOP_N).copy()
    show["article_share"] = (show["article_share"] * 100).map("{:.1f}%".format)
    print(show.to_string())
