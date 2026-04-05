import logging
import polars as pl
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
import numpy as np

logger = logging.getLogger(__name__)

def run_isolation_forest(signals_df: pl.DataFrame) -> pl.DataFrame:
    """Predict anomalies using IsolationForest."""
    try:
        if signals_df is None or len(signals_df) == 0:
            return signals_df
            
        if len(signals_df) < 10:
            logger.warning("Fewer than 10 authors, skipping IsolationForest.")
            return signals_df.with_columns(pl.lit(0.0).alias("if_score"))
            
        # extract features
        features = signals_df.drop("author").to_numpy()
        
        # fit IF
        clf = IsolationForest(contamination=0.05, random_state=42)
        clf.fit(features)
        
        # decision_function yields scores. Lower is more anomalous negative
        # we want norm scores [0, 1] where 1 = most anomalous
        scores = clf.decision_function(features)
        
        # invert so higher is anomalous
        scores = -scores 
        
        scaler = MinMaxScaler()
        norm_scores = scaler.fit_transform(scores.reshape(-1, 1)).flatten()
        
        return signals_df.with_columns(pl.Series("if_score", norm_scores))
        
    except Exception as e:
        logger.error(f"Error in run_isolation_forest: {e}")
        # fallback
        return signals_df.with_columns(pl.lit(0.0).alias("if_score"))
