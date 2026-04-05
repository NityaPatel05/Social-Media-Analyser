import logging
import polars as pl
import math

logger = logging.getLogger(__name__)

def get_early_adopters(df: pl.DataFrame, topic_assignments: list, target_tid: str, spam_scores: dict) -> dict:
    """
    Identify the first 10% of posts in a topic cluster and return their authors.
    Cross reference with spam_scores. Return amplification flag.
    """
    try:
        if df is None or len(df) == 0:
            return {"authors": [], "spam_fraction": 0.0, "amplification_flag": False}
            
        texts = df["full_text"].to_list()
        authors = df["author"].to_list()
        dates = df["created_utc"].to_list()
        
        # We need to filter manually since topic_assignments is a flat list aligning with df rows
        # Assumes df was not reordered from when topic_assignments was made!
        cluster_posts = []
        for i, tid in enumerate(topic_assignments):
            if str(tid) == str(target_tid):
                cluster_posts.append({
                    "author": authors[i],
                    "created_utc": dates[i]
                })
                
        if len(cluster_posts) < 5:
            return {"authors": [], "spam_fraction": 0.0, "amplification_flag": False}
            
        cluster_posts.sort(key=lambda x: x["created_utc"])
        
        cutoff_idx = max(1, math.ceil(len(cluster_posts) * 0.10))
        early_posts = cluster_posts[:cutoff_idx]
        
        early_authors = list(set([p["author"] for p in early_posts]))
        
        spam_count = 0
        for auth in early_authors:
            # check spam Cache
            val = spam_scores.get(auth)
            if val and val.get("spam_score", 0) > 0.5:
                spam_count += 1
                
        spam_fraction = spam_count / len(early_authors) if len(early_authors) > 0 else 0.0
        amplification_flag = spam_fraction > 0.3
        
        return {
            "authors": early_authors,
            "spam_fraction": float(spam_fraction),
            "amplification_flag": amplification_flag
        }
    except Exception as e:
        logger.error(f"Error in get_early_adopters: {e}")
        return {"authors": [], "spam_fraction": 0.0, "amplification_flag": False}
