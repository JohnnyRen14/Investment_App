"""
Financial Data Models

Pydantic models for all financial data structures used in the Investment App.
These models ensure data validation and type safety across the application.

Author: Lebron (Data & Infrastructure Lead)
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class DataSource(str, Enum):
    """Enumeration of supported data sources"""
    YAHOO_FINANCE = "yahoo_finance"
    ALPHA_VANTAGE = "alpha_vantage"
    MANUAL = "manual"


class DataType(str, Enum):
    """Enumeration of data types"""
    STOCK_PRICE = "stock_price"
    FINANCIAL_STATEMENT = "financial_statement"
    MARKET_DATA = "market_data"
    COMPANY_INFO = "company_info"


class StockPrice(BaseModel):
    """Model for stock price data"""
    symbol: str = Field(..., description="Stock symbol")
    date: date = Field(..., description="Price date")
    open_price: Optional[Decimal] = Field(None, description="Opening price")
    high_price: Optional[Decimal] = Field(None, description="High price")
    low_price: Optional[Decimal] = Field(None, description="Low price")
    close_price: Decimal = Field(..., description="Closing price")
    adjusted_close: Optional[Decimal] = Field(None, description="Adjusted closing price")
    volume: Optional[int] = Field(None, description="Trading volume")
    
    @validator('close_price', 'open_price', 'high_price', 'low_price', 'adjusted_close')
    def validate_positive_prices(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Price must be positive')
        return v
    
    @validator('volume')
    def validate_volume(cls, v):
        if v is not None and v < 0:
            raise ValueError('Volume cannot be negative')
        return v


class CompanyInfo(BaseModel):
    """Model for company information"""
    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    sector: Optional[str] = Field(None, description="Business sector")
    industry: Optional[str] = Field(None, description="Industry classification")
    market_cap: Optional[Decimal] = Field(None, description="Market capitalization")
    enterprise_value: Optional[Decimal] = Field(None, description="Enterprise value")
    trailing_pe: Optional[Decimal] = Field(None, description="Trailing P/E ratio")
    forward_pe: Optional[Decimal] = Field(None, description="Forward P/E ratio")
    peg_ratio: Optional[Decimal] = Field(None, description="PEG ratio")
    price_to_book: Optional[Decimal] = Field(None, description="Price to book ratio")
    price_to_sales: Optional[Decimal] = Field(None, description="Price to sales ratio")
    beta: Optional[Decimal] = Field(None, description="Beta coefficient")
    dividend_yield: Optional[Decimal] = Field(None, description="Dividend yield")
    description: Optional[str] = Field(None, description="Company description")
    website: Optional[str] = Field(None, description="Company website")
    employees: Optional[int] = Field(None, description="Number of employees")
    
    @validator('market_cap', 'enterprise_value')
    def validate_positive_values(cls, v):
        if v is not None and v < 0:
            raise ValueError('Value cannot be negative')
        return v


class IncomeStatement(BaseModel):
    """Model for income statement data"""
    symbol: str = Field(..., description="Stock symbol")
    period_ending: date = Field(..., description="Period ending date")
    period_type: str = Field(..., description="Annual or Quarterly")
    revenue: Optional[Decimal] = Field(None, description="Total revenue")
    cost_of_revenue: Optional[Decimal] = Field(None, description="Cost of revenue")
    gross_profit: Optional[Decimal] = Field(None, description="Gross profit")
    operating_expenses: Optional[Decimal] = Field(None, description="Operating expenses")
    operating_income: Optional[Decimal] = Field(None, description="Operating income")
    interest_expense: Optional[Decimal] = Field(None, description="Interest expense")
    pretax_income: Optional[Decimal] = Field(None, description="Pretax income")
    income_tax: Optional[Decimal] = Field(None, description="Income tax")
    net_income: Optional[Decimal] = Field(None, description="Net income")
    eps_basic: Optional[Decimal] = Field(None, description="Basic EPS")
    eps_diluted: Optional[Decimal] = Field(None, description="Diluted EPS")
    shares_outstanding: Optional[Decimal] = Field(None, description="Shares outstanding")
    
    @validator('period_type')
    def validate_period_type(cls, v):
        if v not in ['Annual', 'Quarterly']:
            raise ValueError('Period type must be Annual or Quarterly')
        return v


class BalanceSheet(BaseModel):
    """Model for balance sheet data"""
    symbol: str = Field(..., description="Stock symbol")
    period_ending: date = Field(..., description="Period ending date")
    period_type: str = Field(..., description="Annual or Quarterly")
    total_assets: Optional[Decimal] = Field(None, description="Total assets")
    current_assets: Optional[Decimal] = Field(None, description="Current assets")
    cash_and_equivalents: Optional[Decimal] = Field(None, description="Cash and cash equivalents")
    inventory: Optional[Decimal] = Field(None, description="Inventory")
    total_liabilities: Optional[Decimal] = Field(None, description="Total liabilities")
    current_liabilities: Optional[Decimal] = Field(None, description="Current liabilities")
    long_term_debt: Optional[Decimal] = Field(None, description="Long-term debt")
    total_equity: Optional[Decimal] = Field(None, description="Total shareholders' equity")
    retained_earnings: Optional[Decimal] = Field(None, description="Retained earnings")
    
    @validator('period_type')
    def validate_period_type(cls, v):
        if v not in ['Annual', 'Quarterly']:
            raise ValueError('Period type must be Annual or Quarterly')
        return v


class CashFlowStatement(BaseModel):
    """Model for cash flow statement data"""
    symbol: str = Field(..., description="Stock symbol")
    period_ending: date = Field(..., description="Period ending date")
    period_type: str = Field(..., description="Annual or Quarterly")
    operating_cash_flow: Optional[Decimal] = Field(None, description="Operating cash flow")
    investing_cash_flow: Optional[Decimal] = Field(None, description="Investing cash flow")
    financing_cash_flow: Optional[Decimal] = Field(None, description="Financing cash flow")
    net_cash_flow: Optional[Decimal] = Field(None, description="Net cash flow")
    free_cash_flow: Optional[Decimal] = Field(None, description="Free cash flow")
    capital_expenditures: Optional[Decimal] = Field(None, description="Capital expenditures")
    depreciation: Optional[Decimal] = Field(None, description="Depreciation and amortization")
    
    @validator('period_type')
    def validate_period_type(cls, v):
        if v not in ['Annual', 'Quarterly']:
            raise ValueError('Period type must be Annual or Quarterly')
        return v


class FinancialStatement(BaseModel):
    """Comprehensive financial statement model"""
    symbol: str = Field(..., description="Stock symbol")
    period_ending: date = Field(..., description="Period ending date")
    period_type: str = Field(..., description="Annual or Quarterly")
    income_statement: Optional[IncomeStatement] = None
    balance_sheet: Optional[BalanceSheet] = None
    cash_flow_statement: Optional[CashFlowStatement] = None
    data_source: DataSource = Field(..., description="Source of the data")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


class MarketData(BaseModel):
    """Model for market-wide data"""
    date: date = Field(..., description="Data date")
    risk_free_rate: Optional[Decimal] = Field(None, description="Risk-free rate (10Y Treasury)")
    market_risk_premium: Optional[Decimal] = Field(None, description="Market risk premium")
    sp500_return: Optional[Decimal] = Field(None, description="S&P 500 return")
    vix: Optional[Decimal] = Field(None, description="VIX volatility index")
    data_source: DataSource = Field(..., description="Source of the data")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


class DataQualityMetrics(BaseModel):
    """Model for data quality assessment"""
    symbol: str = Field(..., description="Stock symbol")
    data_source: DataSource = Field(..., description="Source of the data")
    data_type: DataType = Field(..., description="Type of data")
    quality_score: Decimal = Field(..., description="Overall quality score (0-100)")
    completeness_score: Decimal = Field(..., description="Data completeness score (0-100)")
    freshness_score: Decimal = Field(..., description="Data freshness score (0-100)")
    accuracy_score: Decimal = Field(..., description="Data accuracy score (0-100)")
    last_assessed: datetime = Field(default_factory=datetime.now, description="Last assessment timestamp")
    issues: List[str] = Field(default_factory=list, description="List of identified issues")
    
    @validator('quality_score', 'completeness_score', 'freshness_score', 'accuracy_score')
    def validate_score_range(cls, v):
        if not (0 <= v <= 100):
            raise ValueError('Score must be between 0 and 100')
        return v


class StockData(BaseModel):
    """Comprehensive stock data model"""
    symbol: str = Field(..., description="Stock symbol")
    company_info: Optional[CompanyInfo] = None
    current_price: Optional[StockPrice] = None
    historical_prices: List[StockPrice] = Field(default_factory=list)
    financial_statements: List[FinancialStatement] = Field(default_factory=list)
    data_quality: Optional[DataQualityMetrics] = None
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class APIRateLimit(BaseModel):
    """Model for API rate limiting tracking"""
    api_name: str = Field(..., description="API name")
    endpoint: str = Field(..., description="API endpoint")
    requests_made: int = Field(default=0, description="Requests made in current period")
    requests_limit: int = Field(..., description="Request limit for the period")
    reset_time: datetime = Field(..., description="When the limit resets")
    
    @property
    def requests_remaining(self) -> int:
        """Calculate remaining requests"""
        return max(0, self.requests_limit - self.requests_made)
    
    @property
    def is_limit_exceeded(self) -> bool:
        """Check if rate limit is exceeded"""
        return self.requests_made >= self.requests_limit


class CacheEntry(BaseModel):
    """Model for cache entries"""
    key: str = Field(..., description="Cache key")
    data: Dict[str, Any] = Field(..., description="Cached data")
    created_at: datetime = Field(default_factory=datetime.now, description="Cache creation time")
    expires_at: datetime = Field(..., description="Cache expiration time")
    data_source: DataSource = Field(..., description="Source of the cached data")
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return datetime.now() > self.expires_at
    
    @property
    def ttl_seconds(self) -> int:
        """Get time to live in seconds"""
        if self.is_expired:
            return 0
        return int((self.expires_at - datetime.now()).total_seconds())