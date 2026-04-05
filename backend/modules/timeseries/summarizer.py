import logging
import os
import time
import hashlib
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Simple in-process cache: key -> (summary_str, expiry_epoch)
_summary_cache: dict = {}
_CACHE_TTL_SECONDS = 1800  # reuse result for 30 minutes

from config import get_gemini_api_key, mark_gemini_key_exhausted, increment_gemini_key_usage

def get_gemini_summary(text_prompt: str) -> str:
    """Wrapper for gemini call with multi-key daily quota guard."""
    api_key = get_gemini_api_key()
    if not api_key:
        logger.info("All Gemini API keys exhausted or none provided — returning empty summary.")
        return ""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        increment_gemini_key_usage(api_key)
        response = model.generate_content(
            text_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=500,
                temperature=0.3
            )
        )
        logger.info(f"Gemini call successful, tokens approx {len(response.text.split())}")
        return response.text
    except Exception as e:
        err_str = str(e)
        logger.error(f"Gemini API call failed: {e}")
        if "GenerateRequestsPerDay" in err_str or ("429" in err_str and "limit: 20" in err_str) or "Quota exceeded" in err_str:
            mark_gemini_key_exhausted(api_key)
            logger.warning("Gemini daily quota exhausted for this key — marked for 24h.")
        return ""

def summarize_timeseries(weekly_data, anomaly_result: dict = None) -> str:
    """
    Summarize time-series data using Gemini. Results are cached per unique
    input fingerprint for 30 minutes to avoid hammering the daily quota.
    """
    try:
        t0 = time.time()

        # Build a cheap cache key from the input shape so repeated identical
        # requests don't consume quota.
        cache_key = hashlib.md5(
            f"{weekly_data}{anomaly_result}".encode()
        ).hexdigest()
        if cache_key in _summary_cache:
            cached_text, expiry = _summary_cache[cache_key]
            if time.time() < expiry:
                logger.info("summarize_timeseries cache HIT — skipping Gemini call.")
                return cached_text
        
        if anomaly_result is None:
            anomaly_result = {"anomalies": [], "changepoints": []}

        if isinstance(weekly_data, list) and len(weekly_data) >= 2:
            prev = weekly_data[-2].get("count", 0) or 0
            curr = weekly_data[-1].get("count", 0) or 0
            recent_growth = ((curr - prev) / prev) if prev else 0.0
        else:
            recent_growth = 0.0

        anomalies = anomaly_result.get("anomalies", [])
        changepoints = anomaly_result.get("changepoints", [])

        prompt = f"""
        You are a social media analyst. Here is time series data of post volume:
        Anomalies (spikes): {anomalies}
        Changepoints (structural shifts): {changepoints}
        Recent Growth Rate: {recent_growth * 100:.1f}%

        Please provide a plain-language summary of what these trends mean in 2-3 sentences.
        If there are no anomalies or changepoints, note that the volume is stable.
        Focus on interpreting shifts and spikes.
        """
        
        summary = get_gemini_summary(prompt)
        latency = time.time() - t0
        logger.info(f"Gemini summarize_timeseries latency: {latency:.2f}s")

        # On a successful (non-empty) Gemini response, cache it
        if summary:
            _summary_cache[cache_key] = (summary, time.time() + _CACHE_TTL_SECONDS)
        
        if not summary:
            # Fallback template
            has_anoms = len(anomalies) > 0
            has_cps = len(changepoints) > 0
            summary = f"Fallback Summary: This topic has a growth rate of {recent_growth * 100:.1f}%. "
            if has_anoms:
                summary += "We have flagged some days as statistically significant anomalies with high volume. "
            if has_cps:
                summary += "There are structural shifts in the overall volume indicating a change in momentum. "
            if not has_anoms and not has_cps:
                summary += "The specific volume pattern appears stable with no recent extreme spikes."
                
        return summary
    except Exception as e:
        logger.error(f"Error in summarize_timeseries: {e}")
        return "Error analyzing the time-series data."
