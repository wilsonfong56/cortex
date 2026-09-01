"""Dev-only config. No billing, no user DB, no brokerage."""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TICKER_ANALYSIS_TTL = 4 * 3600
MARKET_REPORT_TTL = 12 * 3600
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
