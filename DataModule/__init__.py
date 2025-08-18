"""
DataModule - Financial Data Integration and Management

This module handles all external financial data integration, caching, 
validation, and quality assessment for the Investment App.

Author: Lebron (Data & Infrastructure Lead)
"""

__version__ = "1.0.0"
__author__ = "Lebron"

from .services.data_service import DataService
from .services.yahoo_finance_client import YahooFinanceClient
from .services.alpha_vantage_client import AlphaVantageClient
from .services.cache_service import CacheService
from .services.data_quality_service import DataQualityService
from .models.financial_data import (
    StockData,
    FinancialStatement,
    MarketData,
    DataQualityMetrics
)

__all__ = [
    "DataService",
    "YahooFinanceClient", 
    "AlphaVantageClient",
    "CacheService",
    "DataQualityService",
    "StockData",
    "FinancialStatement",
    "MarketData",
    "DataQualityMetrics"
]