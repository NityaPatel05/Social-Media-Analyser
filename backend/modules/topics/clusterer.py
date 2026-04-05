import logging
import html
import re
import numpy as np
import polars as pl
from bertopic import BERTopic
from bertopic.vectorizers import ClassTfidfTransformer
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer

logger = logging.getLogger(__name__)

# ── Extended stopword list (English + common Reddit noise) ────────────────────
_EXTRA_STOPWORDS = {
    "the", "to", "and", "a", "of", "in", "is", "it", "for", "on", "that",
    "this", "was", "are", "be", "as", "at", "by", "an", "or", "but", "not",
    "with", "from", "have", "had", "has", "he", "she", "they", "we", "you",
    "i", "my", "your", "his", "her", "its", "our", "their", "do", "did",
    "does", "will", "would", "could", "should", "may", "might", "shall",
    "can", "been", "being", "so", "if", "about", "up", "out", "no", "more",
    "just", "what", "all", "get", "got", "like", "one", "also", "into",
    "than", "then", "when", "there", "which", "who", "how", "said", "amp",
    "nbsp", "ampnbsp", "http", "https", "www", "com", "reddit", "post",
    "comment", "deleted", "removed", "edit", "source", "via", "new", "re",
}

def _clean_text(text: str) -> str:
    """Unescape HTML entities and strip noise before vectorization."""
    text = html.unescape(str(text))
    # Remove URLs
    text = re.sub(r"https?://\S+", " ", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove special chars but keep spaces and letters
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else " "


def run_clustering(df: pl.DataFrame, embeddings: np.ndarray, nr_topics: int = 10) -> dict:
    """
    Run BERTopic with stopword-filtered CountVectorizer.
    Returns topics, terms, counts, timeseries.
    """
    try:
        if df is None or len(df) == 0 or len(embeddings) == 0:
            return {"assignments": [], "top_terms": {}, "sizes": {}, "timeseries": {}, "warning": "No data"}

        # ── Clean texts before fitting ────────────────────────────────────────
        raw_texts = df["full_text"].to_list()
        texts = [_clean_text(t) for t in raw_texts]

        n = len(texts)

        # ── Vectorizer with stopwords ─────────────────────────────────────────
        vectorizer_model = CountVectorizer(
            stop_words="english",           # built-in sklearn English stopwords
            min_df=2,                       # ignore very rare terms
            max_df=0.85,                    # ignore terms in >85% of docs (too common)
            ngram_range=(1, 2),             # unigrams + bigrams for richer labels
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",  # letters only, min 2 chars
        )

        # Add our custom extra stopwords on top
        vectorizer_model.set_params(
            stop_words=list(
                set(CountVectorizer(stop_words="english").get_stop_words())
                | _EXTRA_STOPWORDS
            )
        )

        # Reduce term weights for very frequent words across all topics
        ctfidf_model = ClassTfidfTransformer(reduce_frequent_words=True)

        # ── UMAP: 5-component internal (for clustering quality) ───────────────
        umap_model = UMAP(
            n_neighbors=min(15, n - 1),
            n_components=5,
            min_dist=0.0,
            metric="cosine",
            random_state=42,
            low_memory=n > 5000,
        )

        # ── HDBSCAN ───────────────────────────────────────────────────────────
        hdbscan_model = HDBSCAN(
            min_cluster_size=max(5, min(15, n // 20)),
            min_samples=3,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
        )

        # ── Cap nr_topics sensibly ────────────────────────────────────────────
        max_possible = min(nr_topics, max(2, n // 10))
        effective_nr = max_possible if max_possible != nr_topics else nr_topics

        topic_model = BERTopic(
            nr_topics=effective_nr,
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer_model,
            ctfidf_model=ctfidf_model,
            verbose=False,
        )

        topics, _ = topic_model.fit_transform(texts, embeddings)

        topic_info = topic_model.get_topic_info()
        found_topics = len(topic_info) - (1 if -1 in topic_info["Topic"].values else 0)

        warning = ""
        if found_topics < nr_topics:
            warning = f"Requested {nr_topics} topics, but data supports {found_topics} coherent clusters."

        # ── Compile top terms — filter stopwords from labels too ──────────────
        top_terms = {}
        sizes = {}

        for _, row in topic_info.iterrows():
            tid = row["Topic"]

            terms = ""
            if tid != -1:
                topic_words = topic_model.get_topic(tid)
                if topic_words:
                    # Filter out any stopwords that slipped through
                    clean_words = [
                        word for word, _ in topic_words
                        if word.lower() not in _EXTRA_STOPWORDS and len(word) > 2
                    ]
                    terms = ", ".join(clean_words[:10])

            top_terms[str(tid)] = terms
            sizes[str(tid)] = int(row["Count"])

        # ── Daily timeseries ──────────────────────────────────────────────────
        dates = df["created_utc"].dt.date().to_list()
        ts_dict: dict = {}
        for d, tid in zip(dates, topics):
            d_str = str(d)
            t_str = str(tid)
            ts_dict.setdefault(t_str, {})
            ts_dict[t_str][d_str] = ts_dict[t_str].get(d_str, 0) + 1

        formatted_ts = {
            t_str: [{"date": d, "count": cnt} for d, cnt in sorted(dc.items())]
            for t_str, dc in ts_dict.items()
        }

        return {
            "assignments": topics,
            "top_terms": top_terms,
            "sizes": sizes,
            "timeseries": formatted_ts,
            "warning": warning,
        }

    except Exception as e:
        logger.error(f"Error in run_clustering: {e}", exc_info=True)
        return {"assignments": [], "top_terms": {}, "sizes": {}, "timeseries": {}, "warning": "Clustering error."}