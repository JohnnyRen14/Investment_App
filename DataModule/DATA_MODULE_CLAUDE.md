# Data Module - Technical Specification

## 📋 Module Overview
**Purpose**: Handle all external data fetching, validation, caching, and database operations for financial information.

**Core Responsibility**: Provide reliable, validated financial data to other modules while managing data sources, caching strategies, and database persistence.

## 🎯 Module Scope & Boundaries

### ✅ What This Module Handles:
- External API integration (Yahoo Finance, Alpha Vantage)
- Financial data fetching and validation
- Data quality assessment and scoring
- Redis caching management
- Database operations and queries
- Data transformation and normalization
- Rate limiting and API management
- Real-time price updates
- Historical data management

### ❌ What This Module Does NOT Handle:
- DCF calculations (handled by DCF Module)
- User authentication (handled by User Module)
- Portfolio management (handled by Portfolio Module)
- Data visualization (handled by Report Module)

## 🏗️ Technical Architecture

### Database Schema
```sql
-- Stock metadata and information
CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    shares_outstanding BIGINT,
    currency VARCHAR(3) DEFAULT 'USD',
    exchange VARCHAR(50),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Financial statements data
CREATE TABLE financial_statements (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    statement_type VARCHAR(20) NOT NULL, -- 'income', 'balance', 'cashflow'
    period_type VARCHAR(10) NOT NULL,    -- 'annual', 'quarterly'
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,
    data JSONB NOT NULL,
    reported_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, statement_type, period_type, fiscal_year, fiscal_quarter)
);

-- Real-time and historical price data
CREATE TABLE stock_prices (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    open_price DECIMAL(10,4),
    high_price DECIMAL(10,4),
    low_price DECIMAL(10,4),
    close_price DECIMAL(10,4),
    volume BIGINT,
    adjusted_close DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, price_date)
);

-- Data source tracking and reliability
CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(50) UNIQUE NOT NULL,
    api_endpoint VARCHAR(255),
    rate_limit_per_minute INTEGER,
    rate_limit_per_day INTEGER,
    reliability_score DECIMAL(3,2) DEFAULT 1.0,
    last_successful_call TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true
);

-- API call tracking for rate limiting
CREATE TABLE api_call_logs (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES data_sources(id),
    endpoint VARCHAR(255),
    ticker VARCHAR(10),
    response_time_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data quality metrics
CREATE TABLE data_quality_scores (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    completeness_score DECIMAL(3,2),
    accuracy_score DECIMAL(3,2),
    timeliness_score DECIMAL(3,2),
    overall_score DECIMAL(3,2),
    last_assessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Core Classes & Services

#### Data Source Manager
```python
from typing import Dict, List, Optional, Union
from pydantic import BaseModel
import aiohttp
import asyncio
from datetime import datetime, timedelta
import redis
import json

class DataSourceConfig(BaseModel):
    name: str
    base_url: str
    api_key: Optional[str] = None
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 1000
    timeout_seconds: int = 10
    retry_attempts: int = 3

class FinancialDataPoint(BaseModel):
    ticker: str
    data_type: str
    value: Union[float, str, Dict]
    period: str
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    source: str
    timestamp: datetime

class DataSourceManager:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
        self.sources = {
            'yahoo_finance': DataSourceConfig(
                name='yahoo_finance',
                base_url='https://query1.finance.yahoo.com/v8/finance/chart/',
                rate_limit_per_minute=60,
                rate_limit_per_day=2000
            ),
            'alpha_vantage': DataSourceConfig(
                name='alpha_vantage',
                base_url='https://www.alphavantage.co/query',
                api_key=os.getenv('ALPHA_VANTAGE_API_KEY'),
                rate_limit_per_minute=5,
                rate_limit_per_day=500
            )
        }
    
    async def get_stock_data(self, ticker: str, data_type: str) -> Optional[Dict]:
        """
        Get stock data with fallback sources
        """
        # Check cache first
        cached_data = await self.get_cached_data(ticker, data_type)
        if cached_data:
            return cached_data
        
        # Try primary source first, then fallbacks
        for source_name in ['yahoo_finance', 'alpha_vantage']:
            try:
                if await self.check_rate_limit(source_name):
                    data = await self.fetch_from_source(ticker, data_type, source_name)
                    if data:
                        # Cache successful result
                        await self.cache_data(ticker, data_type, data)
                        await self.log_api_call(source_name, ticker, True)
                        return data
            except Exception as e:
                await self.log_api_call(source_name, ticker, False, str(e))
                continue
        
        return None
    
    async def fetch_from_source(self, ticker: str, data_type: str, source_name: str) -> Optional[Dict]:
        """
        Fetch data from specific source
        """
        source_config = self.sources[source_name]
        
        if source_name == 'yahoo_finance':
            return await self.fetch_yahoo_finance(ticker, data_type, source_config)
        elif source_name == 'alpha_vantage':
            return await self.fetch_alpha_vantage(ticker, data_type, source_config)
        
        return None
    
    async def fetch_yahoo_finance(self, ticker: str, data_type: str, config: DataSourceConfig) -> Optional[Dict]:
        """
        Fetch data from Yahoo Finance API
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.timeout_seconds)) as session:
                if data_type == 'price':
                    url = f"{config.base_url}{ticker}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            return self.parse_yahoo_price_data(data)
                
                elif data_type == 'financials':
                    # Yahoo Finance financials endpoint
                    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
                    params = {'modules': 'incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory'}
                    
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            return self.parse_yahoo_financial_data(data)
        
        except Exception as e:
            raise Exception(f"Yahoo Finance API error: {str(e)}")
        
        return None
    
    async def fetch_alpha_vantage(self, ticker: str, data_type: str, config: DataSourceConfig) -> Optional[Dict]:
        """
        Fetch data from Alpha Vantage API
        """
        if not config.api_key:
            raise Exception("Alpha Vantage API key not configured")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config.timeout_seconds)) as session:
                if data_type == 'price':
                    params = {
                        'function': 'TIME_SERIES_DAILY',
                        'symbol': ticker,
                        'apikey': config.api_key
                    }
                elif data_type == 'financials':
                    params = {
                        'function': 'INCOME_STATEMENT',
                        'symbol': ticker,
                        'apikey': config.api_key
                    }
                
                async with session.get(config.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'Error Message' in data:
                            raise Exception(f"Alpha Vantage error: {data['Error Message']}")
                        return self.parse_alpha_vantage_data(data, data_type)
        
        except Exception as e:
            raise Exception(f"Alpha Vantage API error: {str(e)}")
        
        return None
    
    async def check_rate_limit(self, source_name: str) -> bool:
        """
        Check if we can make API call within rate limits
        """
        now = datetime.utcnow()
        minute_key = f"rate_limit:{source_name}:{now.strftime('%Y%m%d%H%M')}"
        day_key = f"rate_limit:{source_name}:{now.strftime('%Y%m%d')}"
        
        source_config = self.sources[source_name]
        
        # Check minute limit
        minute_calls = await self.redis.get(minute_key)
        if minute_calls and int(minute_calls) >= source_config.rate_limit_per_minute:
            return False
        
        # Check daily limit
        day_calls = await self.redis.get(day_key)
        if day_calls and int(day_calls) >= source_config.rate_limit_per_day:
            return False
        
        # Increment counters
        await self.redis.incr(minute_key)
        await self.redis.expire(minute_key, 60)
        await self.redis.incr(day_key)
        await self.redis.expire(day_key, 86400)
        
        return True
    
    async def cache_data(self, ticker: str, data_type: str, data: Dict, ttl: int = 900) -> None:
        """
        Cache data in Redis with TTL
        """
        cache_key = f"financial_data:{ticker}:{data_type}"
        await self.redis.setex(cache_key, ttl, json.dumps(data, default=str))
    
    async def get_cached_data(self, ticker: str, data_type: str) -> Optional[Dict]:
        """
        Get cached data from Redis
        """
        cache_key = f"financial_data:{ticker}:{data_type}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        return None
```

#### Financial Data Service
```python
class FinancialDataService:
    def __init__(self, data_source_manager: DataSourceManager, db_session):
        self.data_manager = data_source_manager
        self.db = db_session
    
    async def get_dcf_input_data(self, ticker: str) -> Dict:
        """
        Get all required data for DCF calculation
        """
        # Get current price and market data
        price_data = await self.data_manager.get_stock_data(ticker, 'price')
        if not price_data:
            raise ValueError(f"Could not fetch price data for {ticker}")
        
        # Get financial statements
        financial_data = await self.data_manager.get_stock_data(ticker, 'financials')
        if not financial_data:
            raise ValueError(f"Could not fetch financial data for {ticker}")
        
        # Get company info
        company_info = await self.get_company_info(ticker)
        
        # Transform data for DCF module
        dcf_data = {
            'ticker': ticker,
            'current_price': price_data.get('current_price'),
            'shares_outstanding': company_info.get('shares_outstanding'),
            'market_cap': company_info.get('market_cap'),
            'revenue_history': self.extract_revenue_history(financial_data),
            'operating_cash_flow': self.extract_cash_flow_history(financial_data),
            'capex': self.extract_capex_history(financial_data),
            'working_capital_changes': self.extract_working_capital_changes(financial_data),
            'total_debt': self.extract_total_debt(financial_data),
            'cash_and_equivalents': self.extract_cash(financial_data),
            'beta': company_info.get('beta', 1.0),
            'risk_free_rate': await self.get_risk_free_rate(),
            'market_risk_premium': 0.06,  # Standard assumption
            'tax_rate': self.calculate_effective_tax_rate(financial_data)
        }
        
        # Validate data completeness
        quality_score = self.assess_data_quality(dcf_data)
        dcf_data['quality_score'] = quality_score
        
        return dcf_data
    
    def extract_revenue_history(self, financial_data: Dict) -> List[float]:
        """
        Extract 5-year revenue history from financial statements
        """
        income_statements = financial_data.get('income_statements', [])
        revenues = []
        
        for statement in sorted(income_statements, key=lambda x: x.get('fiscal_year', 0)):
            revenue = statement.get('total_revenue') or statement.get('revenue')
            if revenue:
                revenues.append(float(revenue))
        
        return revenues[-5:]  # Last 5 years
    
    def extract_cash_flow_history(self, financial_data: Dict) -> List[float]:
        """
        Extract operating cash flow history
        """
        cash_flow_statements = financial_data.get('cash_flow_statements', [])
        cash_flows = []
        
        for statement in sorted(cash_flow_statements, key=lambda x: x.get('fiscal_year', 0)):
            ocf = statement.get('operating_cash_flow')
            if ocf:
                cash_flows.append(float(ocf))
        
        return cash_flows[-5:]  # Last 5 years
    
    def assess_data_quality(self, dcf_data: Dict) -> float:
        """
        Assess quality of data for DCF calculation
        """
        score = 1.0
        required_fields = [
            'current_price', 'shares_outstanding', 'revenue_history',
            'operating_cash_flow', 'capex', 'total_debt'
        ]
        
        # Check completeness
        for field in required_fields:
            if not dcf_data.get(field):
                score -= 0.15
        
        # Check data length
        if len(dcf_data.get('revenue_history', [])) < 3:
            score -= 0.2
        
        if len(dcf_data.get('operating_cash_flow', [])) < 3:
            score -= 0.2
        
        # Check for reasonable values
        if dcf_data.get('current_price', 0) <= 0:
            score -= 0.3
        
        return max(0.0, score)
    
    async def get_real_time_price(self, ticker: str) -> Optional[float]:
        """
        Get real-time stock price
        """
        price_data = await self.data_manager.get_stock_data(ticker, 'price')
        return price_data.get('current_price') if price_data else None
    
    async def get_historical_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get historical price data for a date range
        """
        # Check database first
        cached_prices = await self.get_cached_historical_prices(ticker, start_date, end_date)
        if cached_prices:
            return cached_prices
        
        # Fetch from external API
        price_data = await self.data_manager.get_stock_data(ticker, 'historical_prices')
        if price_data:
            # Store in database
            await self.store_historical_prices(ticker, price_data)
            return price_data
        
        return []
```

## 🔌 API Endpoints

### Data Fetching Endpoints
```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1/data", tags=["financial-data"])

@router.get("/stock/{ticker}/price")
async def get_current_price(
    ticker: str,
    data_service: FinancialDataService = Depends(get_data_service)
):
    """Get current stock price"""
    try:
        price = await data_service.get_real_time_price(ticker.upper())
        if price is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Price data not available for {ticker}"
            )
        return {"ticker": ticker.upper(), "price": price, "timestamp": datetime.utcnow()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching price data: {str(e)}"
        )

@router.get("/stock/{ticker}/dcf-data")
async def get_dcf_data(
    ticker: str,
    current_user_id: int = Depends(get_user_id),
    data_service: FinancialDataService = Depends(get_data_service)
):
    """Get all data required for DCF calculation"""
    try:
        dcf_data = await data_service.get_dcf_input_data(ticker.upper())
        return dcf_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching financial data: {str(e)}"
        )

@router.get("/stock/{ticker}/historical")
async def get_historical_data(
    ticker: str,
    start_date: str,
    end_date: str,
    data_service: FinancialDataService = Depends(get_data_service)
):
    """Get historical price data"""
    try:
        historical_data = await data_service.get_historical_prices(
            ticker.upper(), start_date, end_date
        )
        return {"ticker": ticker.upper(), "data": historical_data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching historical data: {str(e)}"
        )

@router.get("/data-quality/{ticker}")
async def get_data_quality_score(
    ticker: str,
    data_service: FinancialDataService = Depends(get_data_service)
):
    """Get data quality assessment for a ticker"""
    try:
        dcf_data = await data_service.get_dcf_input_data(ticker.upper())
        quality_score = data_service.assess_data_quality(dcf_data)
        
        return {
            "ticker": ticker.upper(),
            "quality_score": quality_score,
            "assessment_time": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assessing data quality: {str(e)}"
        )
```

## 🔗 Module Interfaces

### Outgoing Dependencies
```python
# User Module - for authentication
from user_module import get_user_id

# No other direct module dependencies
# This module is foundational and provides data to others
```

### Incoming Dependencies
```python
# Services provided to other modules
class DataInterface:
    async def get_financial_data_for_dcf(self, ticker: str) -> Dict:
        """Primary interface for DCF Module"""
        pass
    
    async def get_current_stock_price(self, ticker: str) -> float:
        """Interface for Portfolio Module"""
        pass
    
    async def get_company_info(self, ticker: str) -> Dict:
        """Interface for Report Module"""
        pass
    
    async def validate_ticker(self, ticker: str) -> bool:
        """Validate if ticker exists and has data"""
        pass
```

## 🧪 Testing Strategy

### Unit Tests
```python
import pytest
from unittest.mock import AsyncMock, Mock
import aiohttp

class TestDataSourceManager:
    @pytest.mark.asyncio
    async def test_rate_limit_check(self):
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        
        manager = DataSourceManager(redis_mock, Mock())
        
        # Should allow call when no previous calls
        can_call = await manager.check_rate_limit('yahoo_finance')
        assert can_call is True
        
        # Should increment counters
        assert redis_mock.incr.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_operations(self):
        redis_mock = AsyncMock()
        manager = DataSourceManager(redis_mock, Mock())
        
        # Test caching
        test_data = {"price": 150.0, "volume": 1000000}
        await manager.cache_data("AAPL", "price", test_data)
        
        redis_mock.setex.assert_called_once()
        
        # Test cache retrieval
        redis_mock.get.return_value = '{"price": 150.0, "volume": 1000000}'
        cached = await manager.get_cached_data("AAPL", "price")
        
        assert cached["price"] == 150.0

class TestFinancialDataService:
    @pytest.mark.asyncio
    async def test_dcf_data_extraction(self):
        mock_manager = AsyncMock()
        mock_manager.get_stock_data.side_effect = [
            {"current_price": 150.0},  # price data
            {  # financial data
                "income_statements": [
                    {"fiscal_year": 2023, "total_revenue": 1000000},
                    {"fiscal_year": 2022, "total_revenue": 950000}
                ],
                "cash_flow_statements": [
                    {"fiscal_year": 2023, "operating_cash_flow": 200000},
                    {"fiscal_year": 2022, "operating_cash_flow": 180000}
                ]
            }
        ]
        
        service = FinancialDataService(mock_manager, Mock())
        
        # Mock company info
        service.get_company_info = AsyncMock(return_value={
            "shares_outstanding": 1000000,
            "market_cap": 150000000,
            "beta": 1.2
        })
        
        dcf_data = await service.get_dcf_input_data("AAPL")
        
        assert dcf_data["ticker"] == "AAPL"
        assert dcf_data["current_price"] == 150.0
        assert len(dcf_data["revenue_history"]) == 2
    
    def test_data_quality_assessment(self):
        service = FinancialDataService(Mock(), Mock())
        
        # Complete data
        complete_data = {
            "current_price": 150.0,
            "shares_outstanding": 1000000,
            "revenue_history": [1000, 1100, 1200, 1300, 1400],
            "operating_cash_flow": [200, 220, 240, 260, 280],
            "capex": [50, 55, 60, 65, 70],
            "total_debt": 500000
        }
        
        score = service.assess_data_quality(complete_data)
        assert score >= 0.8
        
        # Incomplete data
        incomplete_data = {
            "current_price": 150.0,
            "revenue_history": [1000, 1100]  # Only 2 years
        }
        
        score = service.assess_data_quality(incomplete_data)
        assert score < 0.5
```

### Integration Tests
```python
class TestDataEndpoints:
    @pytest.mark.asyncio
    async def test_get_current_price(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/data/stock/AAPL/price")
        
        assert response.status_code == 200
        data = response.json()
        assert "ticker" in data
        assert "price" in data
        assert data["ticker"] == "AAPL"
        assert isinstance(data["price"], (int, float))
    
    @pytest.mark.asyncio
    async def test_get_dcf_data(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/data/stock/AAPL/dcf-data")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "ticker", "current_price", "revenue_history",
            "operating_cash_flow", "quality_score"
        ]
        
        for field in required_fields:
            assert field in data
```

## 📊 Performance Requirements

### API Response Times
- Current price: < 200ms
- DCF data compilation: < 1 second
- Historical data: < 500ms
- Data quality assessment: < 300ms

### Caching Strategy
- Real-time prices: 30 seconds TTL
- Financial statements: 24 hours TTL
- Company info: 7 days TTL
- Historical prices: 1 hour TTL

### Rate Limiting
- Yahoo Finance: 60 calls/minute, 2000/day
- Alpha Vantage: 5 calls/minute, 500/day
- Graceful degradation when limits reached

## 🚀 Deployment Considerations

### Environment Variables
```bash
ALPHA_VANTAGE_API_KEY=your_api_key
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://user:pass@localhost/db
DATA_CACHE_TTL=900
RATE_LIMIT_ENABLED=true
```

### Error Handling
- Circuit breaker pattern for external APIs
- Automatic failover between data sources
- Comprehensive logging of API failures
- Data validation and sanitization

---

This module serves as the reliable data foundation for the entire Investment App platform.