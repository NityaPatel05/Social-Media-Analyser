import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def classify_stage(dates: list, counts: list, growth_rate: float, global_max_date: datetime) -> dict:
    """
    Assign categorical lifecycle stage to a topic.
    """
    try:
        if not counts or len(counts) == 0:
             return {"stage": "DEAD", "badge_emoji": "⚫"}
             
        total_posts = sum(counts)
        if total_posts < 3:
            return {"stage": "DEAD", "badge_emoji": "⚫"}
            
        # Check if no posts in last 7 days of dataset timeframe (global_max_date)
        if dates and len(dates) > 0:
            last_post_date = dates[-1]
            if isinstance(last_post_date, str):
                last_post_date = datetime.strptime(last_post_date, "%Y-%m-%d").date()
            if isinstance(global_max_date, str):
                global_max_date = datetime.strptime(global_max_date, "%Y-%m-%d").date()
            elif isinstance(global_max_date, datetime):
                global_max_date = global_max_date.date()
                
            delta_days = (global_max_date - last_post_date).days
            if delta_days >= 7:
                 return {"stage": "DEAD", "badge_emoji": "⚫"}
                 
        # Evaluate current metrics
        current_volume = counts[-1]
        peak_volume = max(counts)
        
        if growth_rate > 0.2 and current_volume < (peak_volume * 0.7):
            return {"stage": "EMERGING", "badge_emoji": "🟢"}
            
        if abs(growth_rate) <= 0.2 and current_volume >= (peak_volume * 0.7):
            return {"stage": "PEAKING", "badge_emoji": "🔵"}
            
        if growth_rate < -0.1 and current_volume > 0:
            return {"stage": "DECLINING", "badge_emoji": "🟡"}
            
        # Default or fallback conditions that don't match strict rules cleanly
        # If it's a single day or we're at boundary
        return {"stage": "EMERGING", "badge_emoji": "🟢", "note": "May still be active beyond dataset range"}
        
    except Exception as e:
        logger.error(f"Error in classify_stage: {e}")
        return {"stage": "UNKNOWN", "badge_emoji": "⚪"}
