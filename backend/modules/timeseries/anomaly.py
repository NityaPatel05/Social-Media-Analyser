import logging
import math
import numpy as np
import polars as pl
import ruptures as rpt
from scipy.stats import zscore

logger = logging.getLogger(__name__)

def detect_anomalies(daily_df) -> dict:
    """
    Detect anomalies using Z-score (>2.0) and ruptures PELT for changepoints.
    """
    try:
        if daily_df is None or len(daily_df) == 0:
            return {"anomalies": [], "changepoints": [], "message": "No data."}

        if isinstance(daily_df, list):
            # Guard: items must be dicts; skip any non-dict items
            dict_items = [item for item in daily_df if isinstance(item, dict)]
            if not dict_items:
                return {"anomalies": [], "changepoints": [], "message": "No valid data items."}
            counts = np.array([item.get("count", 0) for item in dict_items], dtype=float)
            dates = [item.get("date") for item in dict_items]
        else:
            counts = daily_df["count"].to_numpy()
            dates = daily_df["date"].to_list()

        if len(counts) < 7:
            logger.warning("Fewer than 7 data points, skipping anomaly detection.")
            return {
                "anomalies": [], 
                "changepoints": [], 
                "message": "Not enough data points for anomaly detection (requires at least 7)."
            }

        # Z-score anomalies
        z_scores = zscore(counts)
        # zscore returns NaN when std=0 (constant data) — replace non-finite with 0
        z_scores = np.nan_to_num(z_scores, nan=0.0, posinf=0.0, neginf=0.0)
        anomalies = []
        for i, z in enumerate(z_scores):
            if z > 2.0:
                anomalies.append({
                    "date": str(dates[i]),
                    "value": int(counts[i]),
                    "z_score": float(z)
                })

        # Changepoints using ruptures
        algo = rpt.Pelt(model="rbf").fit(counts)
        # using pen=10 as typical default
        result = algo.predict(pen=10)
        
        changepoints = []
        # ruptures returns indices, last one is the length of array
        for idx in result[:-1]:
            if idx < len(dates):
                changepoints.append(str(dates[idx]))

        return {
            "anomalies": anomalies,
            "changepoints": changepoints,
            "message": "Success"
        }

    except Exception as e:
        logger.error(f"Error in detect_anomalies: {e}")
        return {"anomalies": [], "changepoints": [], "message": "Error detecting anomalies."}
