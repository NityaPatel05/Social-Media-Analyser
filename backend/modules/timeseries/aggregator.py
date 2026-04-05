import logging
import polars as pl
from datetime import datetime

logger = logging.getLogger(__name__)

def aggregate_timeseries(df: pl.DataFrame, keyword: str = None, subreddit: str = None, author: str = None, date_start: str = None, date_end: str = None) -> dict:
    """
    Filter data and compute hourly, daily, and weekly aggregated post counts,
    including a 7-day rolling average and daily growth rate.
    """
    try:
        if df is None or len(df) == 0:
            return {"empty": True, "message": "No data available."}

        filtered_df = df.clone()
        
        if keyword:
            filtered_df = filtered_df.filter(pl.col("full_text").str.to_lowercase().str.contains(keyword.lower()))
        if subreddit:
            filtered_df = filtered_df.filter(pl.col("subreddit") == subreddit)
        if author:
            filtered_df = filtered_df.filter(pl.col("author") == author)
        if date_start:
            filtered_df = filtered_df.filter(pl.col("created_utc") >= pl.lit(date_start).str.to_datetime())
        if date_end:
            filtered_df = filtered_df.filter(pl.col("created_utc") <= pl.lit(date_end).str.to_datetime())

        if len(filtered_df) == 0:
            return {"empty": True, "message": "No posts found for the given filters."}

        # Daily aggregation
        daily = filtered_df.group_by(pl.col("created_utc").dt.date().alias("date")).agg(
            pl.len().alias("count")
        ).sort("date")

        # Handle rolling 7-day avg
        if len(daily) > 0:
            daily = daily.with_columns(
                pl.col("count").rolling_mean(window_size=7, min_periods=1).alias("rolling_7d_avg")
            )
            
            # Growth rate
            daily = daily.with_columns(
                pl.col("count").shift(1).alias("prev_count")
            )
            daily = daily.with_columns(
                pl.when(pl.col("prev_count").is_null() | (pl.col("prev_count") == 0))
                .then(0.0)
                .otherwise((pl.col("count") - pl.col("prev_count")) / pl.col("prev_count"))
                .alias("growth_rate")
            ).drop("prev_count")

        # Hourly aggregation
        hourly = filtered_df.group_by(
            pl.col("created_utc").dt.truncate("1h").alias("hour")
        ).agg(pl.len().alias("count")).sort("hour")

        # Weekly aggregation
        weekly = filtered_df.group_by(
            pl.col("created_utc").dt.truncate("1w").alias("week")
        ).agg(pl.len().alias("count")).sort("week")

        # Top contributors (Authors and Subreddits) for the filtered dataset
        top_authors = filtered_df.group_by("author").agg(pl.len().alias("count")).sort("count", descending=True).limit(10).to_dicts()
        top_subreddits = filtered_df.group_by("subreddit").agg(pl.len().alias("count")).sort("count", descending=True).limit(10).to_dicts()

        # Convert back to standard python types for JSON serialization via FastAPI
        return {
            "empty": False,
            "daily": daily.to_dicts(),
            "hourly": hourly.to_dicts(),
            "weekly": weekly.to_dicts(),
            "top_authors": top_authors,
            "top_subreddits": top_subreddits,
        }

    except Exception as e:
        logger.error(f"Error in aggregate_timeseries: {e}")
        return {"empty": True, "message": "An error occurred during aggregation."}
