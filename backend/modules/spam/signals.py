import logging
import urllib.parse
from datetime import datetime
import numpy as np
import polars as pl
from datasketch import MinHash, MinHashLSH
from scipy.stats import entropy
import re

logger = logging.getLogger(__name__)

def extract_domain(text: str) -> str:
    """Extract domain from the first URL found, else return None."""
    if not text: return None
    urls = re.findall(r'(https?://[^\s]+)', text)
    if urls:
        try:
            return urllib.parse.urlparse(urls[0]).netloc
        except:
            return None
    return None

def compute_entropy(intervals):
    if len(intervals) < 2:
        return 0.0
    value_counts = {}
    for val in intervals:
        value_counts[val] = value_counts.get(val, 0) + 1
    total = len(intervals)
    probs = [count / total for count in value_counts.values()]
    return entropy(probs, base=2)

def compute_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Compute 7 behavioral spam signals per author."""
    try:
        if df is None or len(df) == 0:
            return pl.DataFrame()

        # Ensure created_utc is sorted
        df = df.sort(["author", "created_utc"])
        
        # Add extracted domain
        if "url_domain" not in df.columns:
            df = df.with_columns(
                pl.col("full_text").map_elements(extract_domain, return_dtype=pl.String).alias("url_domain")
            )
            
        authors = df["author"].unique().to_list()
        
        results = []
        for author in authors:
            auth_df = df.filter(pl.col("author") == author)
            posts = len(auth_df)
            
            # 1. post_freq_per_hour
            if posts > 1:
                times = auth_df["created_utc"].to_list()
                hours_active = (times[-1] - times[0]).total_seconds() / 3600.0
                if hours_active > 0:
                    post_freq_per_hour = posts / hours_active
                else:
                    post_freq_per_hour = posts
            else:
                post_freq_per_hour = posts
                
            # 2. url_to_post_ratio
            url_posts = len(auth_df.filter(pl.col("url_domain").is_not_null()))
            url_to_post_ratio = url_posts / posts
            
            # 3. domain_repetition_rate
            domain_repetition_rate = 0.0
            if url_posts > 0:
                domains = auth_df.filter(pl.col("url_domain").is_not_null())["url_domain"].to_list()
                most_common = max(set(domains), key=domains.count)
                domain_repetition_rate = domains.count(most_common) / url_posts
                
            # 4. score_to_activity_ratio
            if "score" in auth_df.columns:
                mean_score = auth_df["score"].mean()
                score_to_activity_ratio = mean_score / posts if posts > 0 else 0.0
            else:
                # Fallback if no score column
                score_to_activity_ratio = 0.0
                
            # 5. subreddit_diversity
            unique_subs = auth_df["subreddit"].n_unique()
            subreddit_diversity = unique_subs / posts
            
            # 6. inter_post_entropy
            inter_post_entropy = 0.0
            if posts > 1:
                times_sec = [t.timestamp() for t in auth_df["created_utc"].to_list()]
                intervals = [int(times_sec[i] - times_sec[i-1]) for i in range(1, len(times_sec))]
                inter_post_entropy = compute_entropy(intervals)
                
            # 7. near_duplicate_rate
            near_duplicate_rate = 0.0
            if posts > 1:
                lsh = MinHashLSH(threshold=0.8, num_perm=128)
                texts = auth_df["full_text"].to_list()
                minhashes = []
                for i, text in enumerate(texts):
                    m = MinHash(num_perm=128)
                    if text:
                        for word in text.split():
                            m.update(word.encode('utf8'))
                    lsh.insert(str(i), m)
                    minhashes.append(m)
                    
                duplicates = 0
                for i, m in enumerate(minhashes):
                    res = lsh.query(m)
                    if len(res) > 1:
                        duplicates += 1
                near_duplicate_rate = duplicates / posts
                
            results.append({
                "author": author,
                "post_freq_per_hour": post_freq_per_hour,
                "url_to_post_ratio": url_to_post_ratio,
                "domain_repetition_rate": domain_repetition_rate,
                "score_to_activity_ratio": score_to_activity_ratio,
                "subreddit_diversity": subreddit_diversity,
                "inter_post_entropy": inter_post_entropy,
                "near_duplicate_rate": near_duplicate_rate
            })
            
        signals_df = pl.DataFrame(results)
        
        # Log min/max/mean (skipping author col)
        for col in signals_df.columns[1:]:
            col_min = signals_df[col].min()
            col_max = signals_df[col].max()
            col_mean = signals_df[col].mean()
            logger.info(f"Signal {col} -> Min: {col_min:.3f}, Max: {col_max:.3f}, Mean: {col_mean:.3f}")
            
        return signals_df
        
    except Exception as e:
        logger.error(f"Error in compute_signals: {e}")
        return pl.DataFrame()
