"""Module for profiling dataset schema and value distributions."""

import logging
import polars as pl
from typing import Dict, Any

logger = logging.getLogger(__name__)

def profile_data(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Profile the dataset to find null rates, counts, and top values.
    
    Args:
        df: The Polars DataFrame.
        
    Returns:
        dict: A dictionary containing profile statistics.
    """
    try:
        post_count = df.height
        if post_count == 0:
            logger.warning("Empty DataFrame provided for profiling.")
            return {
                "total_posts": 0,
                "date_range": {"min": None, "max": None},
                "top_authors": [],
                "top_subreddits": [],
                "null_rates": {},
                "language_distribution": []
            }
            
        # Date range
        min_date = df["created_utc"].min()
        max_date = df["created_utc"].max()
        if min_date is not None and not isinstance(min_date, str):
            min_date = min_date.isoformat()
        if max_date is not None and not isinstance(max_date, str):
            max_date = max_date.isoformat()

        # Null rates
        null_rates = {}
        for col in df.columns:
            null_count = df[col].null_count()
            null_rates[col] = float(null_count / post_count)
            
        # We can extract lists from value_counts or group_by depending on Polars version.
        # The safest cross-version aggregation approach:
        # To avoid API mismatches, we'll convert columns to lists for top 10 calculations
        # if the dataset isn't prohibitively huge. But for performance, let's use Polars where possible.
        
        def get_top_k(col_name: str, k: int = 10):
            try:
                # Polars >= 0.19.0
                grouped = df.group_by(col_name).agg(pl.len().alias("count"))
                sorted_grouped = grouped.sort("count", descending=True).head(k)
                return sorted_grouped.to_dicts()
            except Exception:
                try:
                    # Older Polars
                    grouped = df.group_by(col_name).count()
                    sorted_grouped = grouped.sort("count", descending=True).head(k)
                    return sorted_grouped.to_dicts()
                except Exception as e:
                    logger.error(f"Failed to aggregate {col_name}: {e}")
                    return []

        top_authors = get_top_k("author", 10)
        
        # Subreddits (handle if column exists, it should be in data but let's be safe)
        top_subreddits = get_top_k("subreddit", 10) if "subreddit" in df.columns else []
        
        # Language distribution
        lang_dist = get_top_k("lang", 20) if "lang" in df.columns else []

        logger.info(f"Successfully profiled data. Total posts: {post_count}.")
        
        return {
            "total_posts": post_count,
            "date_range": {"min": min_date, "max": max_date},
            "top_authors": top_authors,
            "top_subreddits": top_subreddits,
            "null_rates": null_rates,
            "language_distribution": lang_dist
        }
    except Exception as e:
        logger.error(f"Data profiling failed: {e}")
        return {
            "total_posts": 0,
            "error": str(e)
        }
