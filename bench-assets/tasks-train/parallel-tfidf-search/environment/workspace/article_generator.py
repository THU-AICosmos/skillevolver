#!/usr/bin/env python3
"""
News Article Generator for BM25 Testing

Generates a synthetic corpus of news articles with:
- Category-specific vocabulary and term distributions
- Variable article lengths (simulating real-world variation)
- Multiple categories for diverse content
- Zipf-like term frequency distribution
"""

import argparse
import json
import random
import time
from collections import defaultdict
from dataclasses import asdict, dataclass


# Category-specific vocabularies for realistic news content
CATEGORIES = {
    "sports": {
        "nouns": [
            "championship", "tournament", "league", "season", "match",
            "score", "goal", "point", "player", "coach",
            "team", "stadium", "referee", "penalty", "foul",
            "victory", "defeat", "draw", "record", "medal",
            "athlete", "training", "fitness", "roster", "draft",
            "playoff", "semifinal", "quarterfinal", "overtime", "halftime",
            "tackle", "sprint", "relay", "javelin", "marathon",
            "basketball", "soccer", "football", "tennis", "swimming",
        ],
        "verbs": [
            "win", "lose", "score", "compete", "train",
            "defend", "attack", "tackle", "sprint", "pass",
            "shoot", "dribble", "block", "intercept", "retire",
            "qualify", "eliminate", "dominate", "outperform", "recruit",
        ],
        "adjectives": [
            "undefeated", "dominant", "competitive", "athletic", "professional",
            "amateur", "defensive", "offensive", "injured", "legendary",
            "talented", "seasoned", "rookie", "national", "international",
        ],
    },
    "politics": {
        "nouns": [
            "election", "government", "parliament", "senate", "congress",
            "legislation", "policy", "reform", "amendment", "constitution",
            "candidate", "voter", "ballot", "campaign", "debate",
            "coalition", "opposition", "majority", "minority", "caucus",
            "diplomacy", "treaty", "sanction", "embargo", "summit",
            "budget", "taxation", "regulation", "mandate", "decree",
            "president", "minister", "governor", "mayor", "diplomat",
        ],
        "verbs": [
            "legislate", "govern", "vote", "campaign", "debate",
            "negotiate", "ratify", "veto", "enact", "repeal",
            "endorse", "oppose", "resign", "impeach", "sanction",
            "lobby", "filibuster", "gerrymander", "elect", "inaugurate",
        ],
        "adjectives": [
            "bipartisan", "partisan", "congressional", "federal", "municipal",
            "democratic", "republican", "conservative", "progressive", "moderate",
            "diplomatic", "legislative", "executive", "judicial", "electoral",
        ],
    },
    "entertainment": {
        "nouns": [
            "movie", "film", "series", "show", "episode",
            "actor", "actress", "director", "producer", "screenwriter",
            "performance", "premiere", "audience", "critic", "rating",
            "award", "nomination", "ceremony", "festival", "concert",
            "album", "single", "track", "genre", "soundtrack",
            "theater", "cinema", "studio", "box office", "streaming",
            "celebrity", "interview", "trailer", "sequel", "franchise",
        ],
        "verbs": [
            "perform", "direct", "produce", "star", "premiere",
            "release", "stream", "broadcast", "critique", "review",
            "nominate", "award", "entertain", "inspire", "captivate",
            "compose", "choreograph", "audition", "rehearse", "debut",
        ],
        "adjectives": [
            "blockbuster", "critically-acclaimed", "box-office", "viral", "trending",
            "cinematic", "dramatic", "comedic", "thrilling", "animated",
            "independent", "mainstream", "award-winning", "cult", "iconic",
        ],
    },
    "weather": {
        "nouns": [
            "forecast", "temperature", "precipitation", "humidity", "pressure",
            "storm", "hurricane", "tornado", "blizzard", "drought",
            "rainfall", "snowfall", "heatwave", "coldfront", "warmfront",
            "wind", "gust", "breeze", "monsoon", "cyclone",
            "cloud", "fog", "mist", "hail", "frost",
            "thermometer", "barometer", "satellite", "radar", "warning",
            "advisory", "evacuation", "flooding", "lightning", "thunder",
        ],
        "verbs": [
            "forecast", "predict", "measure", "observe", "track",
            "warn", "evacuate", "shelter", "intensify", "weaken",
            "accumulate", "dissipate", "form", "develop", "approach",
            "subside", "fluctuate", "plummet", "soar", "stabilize",
        ],
        "adjectives": [
            "severe", "tropical", "arctic", "extreme", "mild",
            "humid", "arid", "overcast", "sunny", "cloudy",
            "stormy", "windy", "calm", "freezing", "scorching",
        ],
    },
    "finance": {
        "nouns": [
            "stock", "bond", "commodity", "currency", "index",
            "portfolio", "dividend", "equity", "asset", "liability",
            "revenue", "profit", "loss", "margin", "valuation",
            "interest", "inflation", "recession", "recovery", "boom",
            "trader", "investor", "broker", "analyst", "regulator",
            "exchange", "market", "benchmark", "yield", "spread",
            "futures", "options", "derivatives", "hedge", "leverage",
        ],
        "verbs": [
            "invest", "trade", "hedge", "diversify", "liquidate",
            "appreciate", "depreciate", "rally", "plunge", "fluctuate",
            "capitalize", "underwrite", "audit", "forecast", "rebalance",
            "acquire", "divest", "consolidate", "restructure", "default",
        ],
        "adjectives": [
            "bullish", "bearish", "volatile", "stable", "speculative",
            "fiscal", "monetary", "liquid", "solvent", "overvalued",
            "undervalued", "diversified", "leveraged", "fixed-income", "high-yield",
        ],
    },
}

# Common English filler words
FILLERS = [
    "the", "a", "an", "and", "or", "but", "in", "on", "at",
    "to", "for", "of", "with", "by", "from", "as", "is", "was",
    "are", "were", "been", "be", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may",
    "might", "must", "shall", "can", "need", "this", "that",
    "these", "those", "it", "its", "they", "them", "their",
    "we", "us", "our", "you", "your", "he", "him", "his",
    "she", "her", "which", "who", "whom", "what", "where",
    "when", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "same", "so", "than", "too", "very",
    "just", "also", "now", "here", "there", "then", "once",
]


@dataclass
class Article:
    """Represents a generated news article."""
    article_id: int
    headline: str
    body: str
    category: str
    word_count: int


def weighted_pick(items: list[str], skew: float = 1.3) -> str:
    """Pick an item with Zipf-like weighting favoring earlier items."""
    n = len(items)
    wts = [1.0 / ((i + 1) ** skew) for i in range(n)]
    return random.choices(items, weights=wts, k=1)[0]


def make_sentence(cat_vocab: dict[str, list[str]], length: int = None) -> str:
    """Generate a realistic sentence from category vocabulary."""
    if length is None:
        length = random.randint(7, 22)

    tokens = []
    general_nouns = [
        "time", "year", "people", "way", "day", "world", "life",
        "part", "place", "case", "week", "company", "number",
        "point", "home", "area", "money", "story", "fact",
        "month", "right", "book", "job", "word", "issue",
        "side", "kind", "house", "service", "power", "hour",
        "line", "group", "country", "problem", "change", "effort",
    ]

    for _ in range(length):
        r = random.random()
        if r < 0.28:
            tokens.append(random.choice(FILLERS))
        elif r < 0.52:
            tokens.append(weighted_pick(cat_vocab["nouns"]))
        elif r < 0.72:
            tokens.append(weighted_pick(cat_vocab["verbs"]))
        elif r < 0.84:
            tokens.append(weighted_pick(cat_vocab["adjectives"]))
        elif r < 0.93:
            tokens.append(weighted_pick(general_nouns))
        else:
            tokens.append(random.choice(["reported", "according", "said",
                                         "announced", "confirmed", "stated",
                                         "revealed", "noted", "indicated"]))

    if tokens:
        tokens[0] = tokens[0].capitalize()
        return " ".join(tokens) + "."
    return ""


def make_paragraph(cat_vocab: dict[str, list[str]], num_sentences: int = None) -> str:
    """Generate a paragraph with multiple sentences."""
    if num_sentences is None:
        num_sentences = random.randint(2, 7)
    return " ".join(make_sentence(cat_vocab) for _ in range(num_sentences))


def generate_article(article_id: int, category: str = None,
                     min_words: int = 30, max_words: int = 8000) -> Article:
    """
    Generate a single news article with variable length.
    Uses log-normal distribution for realistic length variation.
    """
    if category is None:
        category = random.choice(list(CATEGORIES.keys()))

    cat_vocab = CATEGORIES[category]

    # Log-normal distribution for high variance in article length
    target_words = int(random.lognormvariate(5.2, 1.4))
    target_words = max(min_words, min(max_words, target_words))

    # Generate headline
    headline_parts = [
        weighted_pick(cat_vocab["adjectives"]).capitalize(),
        weighted_pick(cat_vocab["nouns"]).capitalize(),
        random.choice(["Report", "Update", "Recap", "Briefing",
                       "Highlights", "Breakdown", "Summary", "Coverage"]),
    ]
    headline = " ".join(headline_parts)

    # Generate body paragraphs
    paragraphs = []
    wc = 0
    while wc < target_words:
        para = make_paragraph(cat_vocab)
        paragraphs.append(para)
        wc += len(para.split())

    body = "\n\n".join(paragraphs)

    return Article(
        article_id=article_id,
        headline=headline,
        body=body,
        category=category,
        word_count=len(body.split()),
    )


def generate_articles(num_articles: int, seed: int = 42,
                      min_words: int = 40, max_words: int = 1800) -> list[Article]:
    """
    Generate a corpus of news articles.

    Args:
        num_articles: Number of articles to generate
        seed: Random seed for reproducibility
        min_words: Minimum words per article
        max_words: Maximum words per article
    """
    random.seed(seed)

    cats = list(CATEGORIES.keys())
    cat_probs = [1.0 / len(cats)] * len(cats)

    articles = []
    for i in range(num_articles):
        cat = random.choices(cats, weights=cat_probs, k=1)[0]
        art = generate_article(i, cat, min_words, max_words)
        articles.append(art)

    print(f"Generated {len(articles)} articles.")
    return articles


def save_articles(articles: list[Article], filepath: str):
    """Save articles to JSON file."""
    data = {
        "metadata": {
            "num_articles": len(articles),
            "total_words": sum(a.word_count for a in articles),
            "categories": list(set(a.category for a in articles)),
        },
        "articles": [asdict(a) for a in articles],
    }
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved articles to {filepath}")


def load_articles(filepath: str) -> list[Article]:
    """Load articles from JSON file."""
    with open(filepath) as f:
        data = json.load(f)
    return [Article(**a) for a in data["articles"]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate news article corpus")
    parser.add_argument("--num-articles", type=int, default=5000)
    parser.add_argument("--output", type=str, default="articles.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    articles = generate_articles(args.num_articles, seed=args.seed)
    save_articles(articles, args.output)
