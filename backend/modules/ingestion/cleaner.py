"""Module for cleaning and normalizing ingested data."""

import logging
import hashlib
from datetime import datetime, timezone
import polars as pl
from dateutil import parser
from langdetect import detect
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

def detect_language(text: str) -> str:
    """Detect language of a given text, returning 'unknown' on failure."""
    try:
        if not text or not text.strip():
            return "unknown"
        return detect(text)
    except Exception:
        return "unknown"

def parse_date(date_val: Any) -> Any:
    """Parse date to a timezone-aware UTC datetime."""
    try:
        if date_val is None:
            return None
        if isinstance(date_val, (int, float)):
            return datetime.fromtimestamp(date_val, tz=timezone.utc)
            
        str_val = str(date_val)
        # Attempt to handle string representation of Unix timestamps (e.g., "1612140000")
        try:
            float_val = float(str_val)
            # Basic sanity check: is it in a reasonable Unix timestamp range for social media posts? (>2005)
            if float_val > 1104537600:
                return datetime.fromtimestamp(float_val, tz=timezone.utc)
        except ValueError:
            pass
            
        dt = parser.parse(str_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def generate_hash(author: str, created_utc: datetime, full_text: str) -> str:
    """Generate MD5 hash for deduplication."""
    try:
        # Default to empty strings if None to avoid crashing
        a = str(author) if author is not None else ""
        c = created_utc.isoformat() if created_utc is not None else ""
        t = str(full_text) if full_text is not None else ""
        s = f"{a}_{c}_{t}"
        return hashlib.md5(s.encode('utf-8')).hexdigest()
    except Exception as e:
        logger.error(f"Hash generation failed: {e}")
        return ""

def clean_data(df: pl.DataFrame) -> Tuple[pl.DataFrame, List[Dict[str, Any]]]:
    """
    Clean the loaded DataFrame.
    Returns:
        A tuple of (cleaned_df, bad_rows).
    """
    try:
        if df.height == 0:
            logger.warning("Empty dataframe provided to clean_data.")
            return df, []
            
        initial_count = df.height
        bad_rows = []
        
        # We will process row by row using a dict conversion for easier manipulation given the specific rules
        # Polars map_elements can also be used, but iteration guarantees complex row-level logic safety
        records = df.to_dicts()
        good_records = []
        seen_hashes = set()
        
        for row in records:
            # Handle full_text
            title = row.get("title") or ""
            selftext = row.get("selftext") or ""
            full_text = f"{title} {selftext}".strip()
            row["full_text"] = full_text
            
            # Normalize created_utc
            row["created_utc"] = parse_date(row.get("created_utc"))
            
            # Extract basic fields for malformed checks
            author = row.get("author")
            created_utc = row["created_utc"]
            
            is_malformed = False
            if author is None or str(author).strip() == "":
                is_malformed = True
            elif created_utc is None:
                is_malformed = True
            elif full_text == "":
                is_malformed = True
                
            if is_malformed:
                bad_rows.append(row)
                continue
                
            # Deduplication
            row_hash = generate_hash(author, created_utc, full_text)
            if row_hash in seen_hashes:
                continue
            seen_hashes.add(row_hash)
            
            # Detect language
            row["lang"] = detect_language(full_text)
            
            good_records.append(row)
            
        # Create new cleaned DataFrame
        # Notice that we converted created_utc to python datetime objects, which polars can load
        if len(good_records) > 0:
            cleaned_df = pl.DataFrame(good_records, infer_schema_length=max(10000, len(good_records)))
        else:
            # return empty df with same schema or an entirely empty df
            cleaned_df = pl.DataFrame()
            
        final_count = len(good_records)
        malformed_count = len(bad_rows)
        dupes_count = initial_count - final_count - malformed_count
        
        logger.info(f"Data cleaned. Rows remaining: {final_count}. Deduplicated: {dupes_count}. Malformed: {malformed_count}")
        
        return cleaned_df, bad_rows
        
    except Exception as e:
        logger.error(f"Error during data cleaning: {e}")
        # Return what we got or empty to prevent crashing
        return pl.DataFrame(), []
