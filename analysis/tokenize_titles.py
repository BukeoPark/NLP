"""제목 토큰화: 동의어를 대표어로 바꾼 뒤 한국어는 Kiwi 형태소 분석(사용자 사전 적용),
영어는 소문자 변환 후 단어 단위로 분리한다.

사전 (data/dictionary, 직접 검토해 관리)
  kiwi_user_words.csv : Kiwi 사용자 사전 (word, tag, score, reason)
                        후보는 find_user_dict_candidates.py로 탐색
  synonyms.csv        : 동의어 사전 (lang, concept, pattern, canonical, case_sensitive, note)
                        위에서부터 차례로 적용하므로 긴 표현을 먼저 둔다.
                        영어는 원문 대소문자 기준으로 적용한 뒤 소문자로 바꾼다.

입력: data/processed/google_news_ev_final.csv
출력: data/processed/google_news_ev_tokens.csv
      (title: 원래 제목, title_norm: 동의어 변환 제목,
       tokens: ko는 '형태소/품사', en은 소문자 단어를 공백으로 구분)
      outputs/tables/synonym_matches.csv  (동의어 표현별 출현 횟수)
      outputs/tables/user_dict_effect.csv (사용자 사전 단어별 적용 전후 분석)
      outputs/tables/title_review.csv     (검수용: 원래 제목·변환 제목·적용 동의어·토큰)
"""
import re
from pathlib import Path

import kiwipiepy
import pandas as pd
from kiwipiepy import Kiwi

SRC = Path("data/processed/google_news_ev_final.csv")
OUT = Path("data/processed/google_news_ev_tokens.csv")
USER_DICT = Path("data/dictionary/kiwi_user_words.csv")
SYN_DICT = Path("data/dictionary/synonyms.csv")
SYN_TABLE = Path("outputs/tables/synonym_matches.csv")
EFFECT_TABLE = Path("outputs/tables/user_dict_effect.csv")
REVIEW = Path("outputs/tables/title_review.csv")
N_EXAMPLE = 3
# 영어 단어: 영문·숫자로 이루어지고 내부의 ' ’ - . 는 단어 일부로 유지 (예: trump's, solid-state)
EN_WORD = re.compile(r"[a-z0-9]+(?:['’\-.][a-z0-9]+)*")

df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
user_words = pd.read_csv(USER_DICT, keep_default_na=False)
synonyms = pd.read_csv(SYN_DICT, keep_default_na=False)

kiwi_base = Kiwi()
kiwi = Kiwi()
for r in user_words.itertuples():
    kiwi.add_user_word(r.word, r.tag, float(r.score))
print(f"kiwipiepy {kiwipiepy.__version__}, 사용자 사전 {len(user_words)}개, 동의어 규칙 {len(synonyms)}개")

ko = df["lang"] == "ko"
en = df["lang"] == "en"

# 1) 동의어 변환
#    바꾼 자리는 임시 표식(\x00번호\x00)으로 두어 뒤 규칙이 다시 매칭하지 않게 하고 마지막에 대표어로 바꾼다
df["title_norm"] = df["title"]
applied = {i: [] for i in df.index}
match_rows = []
for k, r in enumerate(synonyms.itertuples()):
    m = df["lang"] == r.lang
    pat = re.compile(r.pattern, 0 if int(r.case_sensitive) else re.I)
    found = []
    for i in df.index[m]:
        hits = pat.findall(df.at[i, "title_norm"])
        if hits:
            found += hits
            applied[i] += [f"{h}→{r.canonical.strip()}" for h in hits]
            df.at[i, "title_norm"] = pat.sub(f"\x00{k}\x00", df.at[i, "title_norm"])
    counts = pd.Series(found, dtype=str).value_counts()
    for txt, c in (counts.items() if len(counts) else [("", 0)]):
        match_rows.append({"lang": r.lang, "concept": r.concept, "matched_text": txt,
                           "canonical": r.canonical.strip(), "count": c, "pattern": r.pattern})
canon = dict(enumerate(synonyms["canonical"]))
df["title_norm"] = df["title_norm"].str.replace(r"\x00(\d+)\x00", lambda mo: canon[int(mo.group(1))], regex=True)
df["title_norm"] = df["title_norm"].str.replace(r"\s+", " ", regex=True).str.strip()
df.loc[en, "title_norm"] = df.loc[en, "title_norm"].str.lower()
df["synonyms_applied"] = pd.Series(applied).map("; ".join)
matches = pd.DataFrame(match_rows)
matches.to_csv(SYN_TABLE, index=False, encoding="utf-8-sig")

pd.set_option("display.width", 200)
print("\n=== 동의어 사전: 제목에서 찾은 표현 ===")
print(matches.loc[matches["count"] > 0, ["lang", "concept", "matched_text", "canonical", "count"]].to_string(index=False))
absent = matches.loc[matches["count"] == 0, ["lang", "pattern", "canonical"]]
if len(absent):
    print("\n[참고] 사전에 있지만 이번 제목에는 없는 표현:")
    print(absent.to_string(index=False))

# 2) 토큰화
ko_tokens = [[(t.form, t.tag) for t in toks] for toks in kiwi.tokenize(df.loc[ko, "title_norm"].tolist())]
df.loc[ko, "tokens"] = [" ".join(f"{f}/{p}" for f, p in toks) for toks in ko_tokens]
df.loc[en, "tokens"] = df.loc[en, "title_norm"].map(lambda s: " ".join(EN_WORD.findall(s)))
df.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"\n저장: {OUT} ({len(df)}건)")

# 검수용: 원래 제목과 변환 제목, 적용된 동의어, 토큰을 한 행에서 비교
review = df[["lang", "source", "published_at", "title", "title_norm", "synonyms_applied", "tokens", "link"]].copy()
review.insert(4, "changed", (df["synonyms_applied"] != "").map({True: "Y", False: ""}))
review.to_csv(REVIEW, index=False, encoding="utf-8-sig")
print(f"검수용 저장: {REVIEW} (동의어 변환된 제목 {(review['changed'] == 'Y').sum()}건)")

# 대표어 집계 확인: 변환 후 대표어(concept)가 하나의 토큰으로 집계된 횟수
concept_rows = []
for (lang, canon), g in matches.groupby(["lang", "concept"], sort=False):
    toks = (f for t in df.loc[df["lang"] == lang, "tokens"] for f in t.split())
    if lang == "ko":
        n = sum(1 for t in toks if t.rsplit("/", 1)[0] == canon)
    else:
        n = sum(1 for t in toks if t == canon or t.startswith(canon + "'") or t.startswith(canon + "’"))
    variants = ", ".join(f"{x}({c})" for x, c in zip(g["matched_text"], g["count"]) if c)
    concept_rows.append({"lang": lang, "concept": canon, "variants_replaced": variants,
                         "token_count_after": n})
print("\n=== 대표어별 변환 후 토큰 수 ===")
print(pd.DataFrame(concept_rows).to_string(index=False))

# 3) 사용자 사전 적용 효과: 제목 속 출현 횟수(더 긴 등록어 안에 포함된 경우 제외)와
#    적용 후 해당 단어가 하나의 형태소로 인식된 횟수 비교
titles = df.loc[ko, "title_norm"].tolist()
base_tokens = list(kiwi_base.tokenize(titles))
rows = []
for r in user_words.itertuples():
    w = r.word
    longer = [lw for lw in user_words["word"] if w in lw and lw != w]
    occ = sum(t.count(w) - sum(t.count(lw) for lw in longer) for t in titles)
    ex_i = next((i for i, t in enumerate(titles) if w in t), None)
    before = ""
    if ex_i is not None:
        s0 = titles[ex_i].find(w)
        before = " ".join(f"{t.form}/{t.tag}" for t in base_tokens[ex_i]
                          if t.start >= s0 and t.end <= s0 + len(w))
    rows.append({
        "word": w, "tag": r.tag, "score": r.score, "reason": r.reason, "occurrences": occ,
        "matched_after": sum(1 for toks in ko_tokens for f, p in toks if f == w and p == r.tag),
        "before_example": before,
    })
eff = pd.DataFrame(rows)
eff.to_csv(EFFECT_TABLE, index=False, encoding="utf-8-sig")
miss = eff[eff["occurrences"] != eff["matched_after"]]
print(f"\n=== 사용자 사전: 출현 횟수와 인식 횟수가 다른 단어 {len(miss)}개 ===")
if len(miss):
    print(miss[["word", "occurrences", "matched_after"]].to_string(index=False))

print("\n=== 한국어: 공백 분리 vs Kiwi 형태소 분석 ===")
for (_, r), toks in list(zip(df[ko].iterrows(), ko_tokens))[:N_EXAMPLE]:
    space = r["title"].split()
    print(f"\n제목: {r['title']}")
    print(f"  공백 분리 ({len(space)}개): {space}")
    print(f"  형태소   ({len(toks)}개): {' '.join(f'{f}/{p}' for f, p in toks)}")

print("\n=== 영어: 동의어 변환·소문자 변환 후 단어 분리 ===")
for _, r in df[en].head(N_EXAMPLE).iterrows():
    words = r["tokens"].split()
    print(f"\n제목: {r['title']}")
    print(f"  변환: {r['title_norm']}")
    print(f"  단어 ({len(words)}개): {words}")
