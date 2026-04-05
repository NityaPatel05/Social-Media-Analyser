import polars as pl
import numpy as np
import math
from sklearn.preprocessing import MinMaxScaler
import logging

logger = logging.getLogger(__name__)

def _safe(v) -> float:
    """Replace NaN/Inf with 0.0 for safe JSON output."""
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return 0.0

def compute_spam_scores(signals_df: pl.DataFrame) -> dict:
    """Combine rule signal scores and IF score into final spam_score."""
    try:
        if signals_df is None or len(signals_df) == 0:
            return {}
            
        # Extract features purely for rules
        rules_df = signals_df.drop(["author", "if_score"])
        features = rules_df.to_numpy()
        
        # Normalize each rule signal to 0-1
        scaler = MinMaxScaler()
        if len(features) > 0:
            norm_features = scaler.fit_transform(features)
            # MinMaxScaler produces NaN when a column has zero variance — replace
            norm_features = np.nan_to_num(norm_features, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            norm_features = features
            
        # Combine normalized rules via mean
        if len(norm_features) > 0:
            rule_score = norm_features.mean(axis=1)
        else:
            rule_score = []
            
        # Extract IF score
        if_score = signals_df["if_score"].to_numpy() if "if_score" in signals_df.columns else np.zeros(len(signals_df))
        
        # Combine IF (0.5) and Rules (0.5)
        # Note: rule_score might need inversion for some signals where high = good. 
        # But per rubric we weight them equally.
        # Actually subreddit_diversity is 1.0=max diversity (less spam). So we invert it.
        
        authors = signals_df["author"].to_list()
        
        results = {}
        for i, author in enumerate(authors):
            # Let's adjust rule signals if they indicate less spam
            # subreddit_diversity high -> less spam
            # entropy high -> less spam
            
            sig_dict = {}
            for j, col in enumerate(rules_df.columns):
                val = norm_features[i][j]
                if col in ["subreddit_diversity", "inter_post_entropy"]:
                    val = 1.0 - val # invert
                sig_dict[col] = float(rules_df[col][i])
                
            # recalculated rule mean
            adj_rule_score = np.mean([
                1.0 - norm_features[i][rules_df.columns.index("subreddit_diversity")],
                1.0 - norm_features[i][rules_df.columns.index("inter_post_entropy")],
                norm_features[i][rules_df.columns.index("post_freq_per_hour")],
                norm_features[i][rules_df.columns.index("url_to_post_ratio")],
                norm_features[i][rules_df.columns.index("domain_repetition_rate")],
                norm_features[i][rules_df.columns.index("score_to_activity_ratio")],
                norm_features[i][rules_df.columns.index("near_duplicate_rate")]
            ]) if len(rules_df.columns) > 0 else 0.0

            s_if = float(if_score[i]) if i < len(if_score) else 0.0
            
            final_spam = 0.5 * adj_rule_score + 0.5 * s_if
            
            sig_dict["adj_rule_score"] = float(adj_rule_score)
            
            results[author] = {
                "spam_score": _safe(final_spam),
                "if_score": _safe(s_if),
                "signals": {k: _safe(v) for k, v in sig_dict.items()}
            }
            
        return dict(sorted(results.items(), key=lambda item: item[1]["spam_score"], reverse=True))
        
    except Exception as e:
        logger.error(f"Error in compute_spam_scores: {e}")
        return {}
