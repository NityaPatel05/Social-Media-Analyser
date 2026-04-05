"""DuckDB client for data loading and querying."""

import duckdb
import logging

logger = logging.getLogger(__name__)

class DuckDBClient:
    """A wrapper for DuckDB connections."""
    def __init__(self):
        self.conn = duckdb.connect(database=':memory:', read_only=False)

    def query(self, query: str):
        """Execute a query and return the relation."""
        try:
            return self.conn.query(query)
        except Exception as e:
            logger.error(f"DuckDB query failed: {e}")
            raise

# Global client
client = DuckDBClient()

def get_duckdb_client() -> DuckDBClient:
    return client
