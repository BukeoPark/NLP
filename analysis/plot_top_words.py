"""언어별 상위 단어 막대그래프와 워드클라우드.

입력: outputs/tables/top_words_ko.csv, outputs/tables/top_words_en.csv (word_frequency.py 결과)
      data/processed/google_news_ev_tokens.csv (언어별 기사 수)
출력: outputs/figures/top_words_bar.png        (언어별 상위 20개, 기사 수 기준)
      outputs/figures/wordcloud_ko.png, wordcloud_en.png (글자 크기: 총 등장 횟수, 색: 기사 비율 구간, 타원형)

- 막대 길이 = 기사 수, 막대 끝 숫자 = 기사 수 (괄호 안 총 등장 횟수)
- 검색어(전기차, ev)는 다른 단어와 비교 대상이 아니므로 회색으로 구분
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from wordcloud import WordCloud

TABLE_DIR = Path("outputs/tables")
FIG_DIR = Path("outputs/figures")
TOP_N = 20
KO_FONT_PATH = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
SEARCH_TERMS = {"ko": "전기차", "en": "ev"}
LABELS = {"ko": "한국어", "en": "영어"}
TOKENS = Path("data/processed/google_news_ev_tokens.csv")

# 색: 단일 계열(파랑) + 검색어용 회색, 텍스트는 잉크 색
BLUE, GRAY = "#2a78d6", "#b5b4ad"
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"

font_manager.fontManager.addfont(KO_FONT_PATH)
plt.rcParams.update({
    "font.family": font_manager.FontProperties(fname=KO_FONT_PATH).get_name(),
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK,
})

N_ARTICLES = pd.read_csv(TOKENS, usecols=["lang"])["lang"].value_counts().to_dict()
tables = {lang: pd.read_csv(TABLE_DIR / f"top_words_{lang}.csv") for lang in LABELS}

# 1) 막대그래프
fig, axes = plt.subplots(1, 2, figsize=(13, 8.5))
for ax, lang in zip(axes, LABELS):
    t = tables[lang].head(TOP_N).iloc[::-1]
    colors = [GRAY if w == SEARCH_TERMS[lang] else BLUE for w in t["word"]]
    ax.barh(t["word"], t["article_count"], color=colors, height=0.7, edgecolor=SURFACE, linewidth=2)
    xmax = t["article_count"].max()
    for y, (a, c) in enumerate(zip(t["article_count"], t["total_count"])):
        ax.text(a + xmax * 0.01, y, f"{a} ({c})", va="center", fontsize=9, color=INK2)
    ax.set_xlim(0, xmax * 1.15)
    ax.set_title(f"{LABELS[lang]} 상위 {TOP_N}개 단어 (기사 {N_ARTICLES[lang]}건)",
                 loc="left", fontsize=13, pad=10)
    ax.set_xlabel("등장한 기사 수 (건)")
    ax.tick_params(axis="y", length=0, labelsize=10)
    ax.grid(axis="x", color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
fig.suptitle("언어별 자주 나온 단어 (최근 30일 전기차 뉴스 제목)", x=0.01, ha="left", fontsize=15)
fig.text(0.01, 0.01,
         "막대 끝 숫자: 기사 수 (총 등장 횟수) · 회색: 검색어 · "
         "한국어는 명사(NNG·NNP), 영어는 불용어·숫자 제외 · 동의어 변환 후 집계",
         fontsize=9, color=INK2)
fig.tight_layout(rect=(0, 0.03, 1, 0.96))
fig.savefig(FIG_DIR / "top_words_bar.png", dpi=150)
plt.close(fig)

# 2) 워드클라우드
#    글자 크기 = 총 등장 횟수, 색 = 등장 기사 비율 구간
#    검색어만 주황 강조, 나머지는 파랑 한 계열에서 비율이 높을수록 진하게
#    타원형 배치, 굵은 글꼴(Noto Sans KR Bold, 없으면 AppleGothic), 단어 80개
WC_FONT_PATH = next((f for f in [Path.home() / "Library/Fonts/NotoSansKR-Bold.ttf",
                                 Path("/Library/Fonts/NotoSansKR-Bold.ttf")] if f.exists()), KO_FONT_PATH)
WC_TIERS = [  # (기사 비율 하한, 색, 범례 이름)
    (0.50, "#e0612b", "50% 이상"),
    (0.10, "#0d366b", "10~50%"),
    (0.05, "#1c5cab", "5~10%"),
    (0.03, "#3987e5", "3~5%"),
    (0.00, "#8fa7c4", "3% 미만"),
]
WC_MAX_WORDS = 80
W, H = 1800, 1100
yy, xx = np.ogrid[:H, :W]
WC_MASK = np.where(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2 <= 1, 0, 255).astype(np.uint8)
title_font = font_manager.FontProperties(fname=str(WC_FONT_PATH))

for lang in LABELS:
    t = tables[lang].head(WC_MAX_WORDS)
    freq = dict(zip(t["word"], t["total_count"]))
    share = dict(zip(t["word"], t["article_share"]))
    tier_of = {w: next(i for i, (lo, _, _) in enumerate(WC_TIERS) if share[w] >= lo) for w in freq}

    wc = WordCloud(font_path=str(WC_FONT_PATH), mask=WC_MASK, background_color="white",
                   max_words=WC_MAX_WORDS, prefer_horizontal=1.0, random_state=7, margin=10,
                   min_font_size=16, max_font_size=260, relative_scaling=0.55,
                   color_func=lambda word, **_: WC_TIERS[tier_of[word]][1]).generate_from_frequencies(freq)

    fig = plt.figure(figsize=(12, 8.6), facecolor="white")
    ax = fig.add_axes((0.03, 0.1, 0.94, 0.76))
    ax.imshow(wc, interpolation="lanczos")
    ax.axis("off")
    fig.text(0.04, 0.945, f"{LABELS[lang]} 전기차 뉴스 제목 키워드", fontproperties=title_font,
             fontsize=19, color=INK, va="center")
    fig.text(0.04, 0.905, f"최근 30일 기사 {N_ARTICLES[lang]}건 · 상위 {len(freq)}개 단어 · "
             "글자 크기는 등장 횟수, 색은 단어가 나온 기사 비율", fontsize=10.5, color=INK2, va="center")
    counts = pd.Series(tier_of).value_counts()
    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=9, color=c,
                          label=f"{name}  {counts.get(i, 0)}개")
               for i, (_, c, name) in enumerate(WC_TIERS)]
    fig.legend(handles=handles, loc="lower center", ncol=len(WC_TIERS), frameon=False,
               fontsize=10, labelcolor=INK2, handletextpad=0.3, columnspacing=2.2,
               bbox_to_anchor=(0.5, 0.035))
    fig.savefig(FIG_DIR / f"wordcloud_{lang}.png", dpi=150, facecolor="white")
    plt.close(fig)

print("저장:", *sorted(p.as_posix() for p in FIG_DIR.glob("*.png")), sep="\n  ")
