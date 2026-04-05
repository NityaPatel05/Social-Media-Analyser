"""Module for loading data into the application."""

import os
import logging
import polars as pl
from database.duckdb_client import get_duckdb_client

logger = logging.getLogger(__name__)

def load_data(file_path: str) -> pl.DataFrame:
    """Load JSONL data using DuckDB and returning a Polars DataFrame.
    
    Args:
        file_path (str): The path to the data.jsonl file.
        
    Returns:
        pl.DataFrame: The loaded data as a Polars DataFrame.
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found at {file_path}")
            
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        client = get_duckdb_client()
        
        # Natively parse JSONL in Python to avoid DuckDB/PyArrow heterogeneous Struct/UUID Extension panics 
        import json
        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                # The valuable fields in our Reddit dump are nested under 'data'
                record_data = json.loads(line).get("data", {})
                
                # Filter only scalar values to prevent Polars from panicking over ragged arrays/structs
                flat_record = {}
                for k, v in record_data.items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        flat_record[k] = v
                records.append(flat_record)
                
        df = pl.DataFrame(records, infer_schema_length=10000)
        
        row_count = len(df)
        logger.info(f"Successfully loaded {row_count} rows from {file_path} ({file_size_mb:.2f} MB).")
        return df
        
    except FileNotFoundError as fnf_err:
        logger.error(f"File not found: {fnf_err}")
        raise
    except Exception as e:
        logger.error(f"Failed to load data from {file_path}: {e}")
        raise
