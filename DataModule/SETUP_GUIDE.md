# Data Module - Development Setup Guide

## 📋 Module Overview
**Responsibility**: Handle all external data fetching, validation, caching, and database operations for financial information.

## 🎯 What's Already Set Up
- ✅ Project structure with backend/frontend folders
- ✅ FastAPI main application (`backend/main.py`)
- ✅ Redis configuration in docker-compose.yml
- ✅ Database structure defined
- ✅ Module specification (`DATA_MODULE_CLAUDE.md`)

## 🚀 Your Development Tasks

### 1. Backend Implementation
**Location**: `backend/app/api/data/`

**Files to Create**:
```
backend/app/api/data/
├── __init__.py
├── routes.py          # Data fetching endpoints
├── schemas.py         # Pydantic models for financial data
├── services.py        # Data processing services
├── sources.py         # External API integrations
└── validators.py      # Data quality validation
```

**Key Components to Implement**:
- `DataSourceManager` class (from specification)
- `FinancialDataService` class (from specification)
- Yahoo Finance API integration
- Alpha Vantage API integration
- Redis caching layer
- Data quality assessment

### 2. Database Models
**Location**: `backend/app/models/`

**Files to Create**:
```
backend/app/models/
├── financial_data.py  # Financial data models
├── data_sources.py    # Data source tracking models
└── market_data.py     # Market data models
```

**Models to Implement**:
- `Stock` model
- `FinancialStatement` model
- `StockPrice` model
- `DataSource` model
- `APICallLog` model
- `DataQualityScore` model

### 3. Frontend Integration
**Location**: `frontend/src/services/`

**Services to Create**:
```
frontend/src/services/
├── dataService.ts     # Data fetching service
├── stockService.ts    # Stock-specific operations
└── cacheService.ts    # Client-side caching
```

## 🔧 Development Environment Setup

### Backend Setup
1. **Install Additional Dependencies**:
```bash
cd backend
pip install yfinance alpha-vantage aiohttp aioredis httpx pandas numpy python-dateutil
```

2. **Set Up Environment Variables**:
```bash
# Add to .env file
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
YAHOO_FINANCE_API_KEY=your_yahoo_finance_api_key_if_needed
REDIS_URL=redis://localhost:6379
RATE_LIMIT_ENABLED=true
CACHE_TTL_SECONDS=900
DATA_CACHE_TTL=1800
```

3. **Create Database Models**:
```python
# backend/app/models/financial_data.py
from sqlalchemy import Column, Integer, String, Date, DateTime, DECIMAL, Boolean, Text, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class Stock(Base):
    __tablename__ = "stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    company_name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(BigInteger)
    shares_outstanding = Column(BigInteger)
    currency = Column(String(3), default='USD')
    exchange = Column(String(50))
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    financial_statements = relationship("FinancialStatement", back_populates="stock")
    stock_prices = relationship("StockPrice", back_populates="stock")

class FinancialStatement(Base):
    __tablename__ = "financial_statements"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    statement_type = Column(String(20), nullable=False)  # 'income', 'balance', 'cashflow'
    period_type = Column(String(10), nullable=False)     # 'annual', 'quarterly'
    fiscal_year = Column(Integer, nullable=False)
    fiscal_quarter = Column(Integer)
    data = Column(JSONB, nullable=False)
    reported_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="financial_statements")
    
    __table_args__ = (
        Index('ix_financial_statements_unique', 'stock_id', 'statement_type', 'period_type', 'fiscal_year', 'fiscal_quarter', unique=True),
    )

class StockPrice(Base):
    __tablename__ = "stock_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    price_date = Column(Date, nullable=False)
    open_price = Column(DECIMAL(10,4))
    high_price = Column(DECIMAL(10,4))
    low_price = Column(DECIMAL(10,4))
    close_price = Column(DECIMAL(10,4))
    volume = Column(BigInteger)
    adjusted_close = Column(DECIMAL(10,4))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    stock = relationship("Stock", back_populates="stock_prices")
    
    __table_args__ = (
        Index('ix_stock_prices_unique', 'stock_id', 'price_date', unique=True),
    )

class DataSource(Base):
    __tablename__ = "data_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(50), unique=True, nullable=False)
    api_endpoint = Column(String(255))
    rate_limit_per_minute = Column(Integer)
    rate_limit_per_day = Column(Integer)
    reliability_score = Column(DECIMAL(3,2), default=1.0)
    last_successful_call = Column(DateTime(timezone=True))
    consecutive_failures = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
```

4. **Create Data Source Manager**:
```python
# backend/app/api/data/sources.py
from typing import Dict, List, Optional, Union
import aiohttp
import asyncio
from datetime import datetime, timedelta
import aioredis
import json
import yfinance as yf
from alpha_vantage.timeseries import TimeSeries
import os

class DataSourceManager:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
        self.sources = {
            'yahoo_finance': {
                'name': 'yahoo_finance',
                'rate_limit_per_minute': 60,
                'rate_limit_per_day': 2000,
                'timeout_seconds': 10
            },
            'alpha_vantage': {
                'name': 'alpha_vantage',
                'api_key': os.getenv('ALPHA_VANTAGE_API_KEY'),
                'rate_limit_per_minute': 5,
                'rate_limit_per_day': 500,
                'timeout_seconds': 10
            }
        }
    
    async def get_stock_data(self, ticker: str, data_type: str) -> Optional[Dict]:
        """Get stock data with fallback sources"""
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
    
    async def fetch_yahoo_finance(self, ticker: str, data_type: str) -> Optional[Dict]:
        """Fetch data from Yahoo Finance"""
        try:
            stock = yf.Ticker(ticker)
            
            if data_type == 'price':
                hist = stock.history(period="1d")
                if not hist.empty:
                    latest = hist.iloc[-1]
                    return {
                        'current_price': float(latest['Close']),
                        'volume': int(latest['Volume']),
                        'high': float(latest['High']),
                        'low': float(latest['Low']),
                        'open': float(latest['Open'])
                    }
            
            elif data_type == 'financials':
                info = stock.info
                financials = stock.financials
                balance_sheet = stock.balance_sheet
                cash_flow = stock.cashflow
                
                return {
                    'company_info': {
                        'company_name': info.get('longName'),
                        'sector': info.get('sector'),
                        'industry': info.get('industry'),
                        'market_cap': info.get('marketCap'),
                        'shares_outstanding': info.get('sharesOutstanding'),
                        'beta': info.get('beta')
                    },
                    'income_statements': self.parse_yahoo_financials(financials),
                    'balance_sheets': self.parse_yahoo_financials(balance_sheet),
                    'cash_flow_statements': self.parse_yahoo_financials(cash_flow)
                }
            
            elif data_type == 'historical_prices':
                hist = stock.history(period="5y")
                return {
                    'prices': [
                        {
                            'date': date.strftime('%Y-%m-%d'),
                            'open': float(row['Open']),
                            'high': float(row['High']),
                            'low': float(row['Low']),
                            'close': float(row['Close']),
                            'volume': int(row['Volume'])
                        }
                        for date, row in hist.iterrows()
                    ]
                }
                
        except Exception as e:
            raise Exception(f"Yahoo Finance API error: {str(e)}")
        
        return None
    
    async def fetch_alpha_vantage(self, ticker: str, data_type: str) -> Optional[Dict]:
        """Fetch data from Alpha Vantage"""
        api_key = self.sources['alpha_vantage']['api_key']
        if not api_key:
            raise Exception("Alpha Vantage API key not configured")
        
        try:
            ts = TimeSeries(key=api_key, output_format='pandas')
            
            if data_type == 'price':
                data, meta_data = ts.get_quote_endpoint(symbol=ticker)
                if not data.empty:
                    return {
                        'current_price': float(data['05. price'].iloc[0]),
                        'volume': int(data['06. volume'].iloc[0]),
                        'high': float(data['03. high'].iloc[0]),
                        'low': float(data['04. low'].iloc[0]),
                        'open': float(data['02. open'].iloc[0])
                    }
            
            elif data_type == 'historical_prices':
                data, meta_data = ts.get_daily(symbol=ticker, outputsize='full')
                return {
                    'prices': [
                        {
                            'date': date.strftime('%Y-%m-%d'),
                            'open': float(row['1. open']),
                            'high': float(row['2. high']),
                            'low': float(row['3. low']),
                            'close': float(row['4. close']),
                            'volume': int(row['5. volume'])
                        }
                        for date, row in data.iterrows()
                    ]
                }
                
        except Exception as e:
            raise Exception(f"Alpha Vantage API error: {str(e)}")
        
        return None
    
    async def check_rate_limit(self, source_name: str) -> bool:
        """Check if we can make API call within rate limits"""
        now = datetime.utcnow()
        minute_key = f"rate_limit:{source_name}:{now.strftime('%Y%m%d%H%M')}"
        day_key = f"rate_limit:{source_name}:{now.strftime('%Y%m%d')}"
        
        source_config = self.sources[source_name]
        
        # Check minute limit
        minute_calls = await self.redis.get(minute_key)
        if minute_calls and int(minute_calls) >= source_config['rate_limit_per_minute']:
            return False
        
        # Check daily limit
        day_calls = await self.redis.get(day_key)
        if day_calls and int(day_calls) >= source_config['rate_limit_per_day']:
            return False
        
        # Increment counters
        await self.redis.incr(minute_key)
        await self.redis.expire(minute_key, 60)
        await self.redis.incr(day_key)
        await self.redis.expire(day_key, 86400)
        
        return True
    
    async def cache_data(self, ticker: str, data_type: str, data: Dict, ttl: int = 900) -> None:
        """Cache data in Redis with TTL"""
        cache_key = f"financial_data:{ticker}:{data_type}"
        await self.redis.setex(cache_key, ttl, json.dumps(data, default=str))
    
    async def get_cached_data(self, ticker: str, data_type: str) -> Optional[Dict]:
        """Get cached data from Redis"""
        cache_key = f"financial_data:{ticker}:{data_type}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        return None
    
    def parse_yahoo_financials(self, df) -> List[Dict]:
        """Parse Yahoo Finance financial data"""
        if df is None or df.empty:
            return []
        
        result = []
        for date, row in df.iterrows():
            fiscal_year = date.year
            data_dict = {}
            
            for item, value in row.items():
                if pd.notna(value):
                    data_dict[item.lower().replace(' ', '_')] = float(value)
            
            result.append({
                'fiscal_year': fiscal_year,
                'data': data_dict
            })
        
        return result
```

5. **Create Financial Data Service**:
```python
# backend/app/api/data/services.py
from typing import Dict, List, Optional
from .sources import DataSourceManager

class FinancialDataService:
    def __init__(self, data_source_manager: DataSourceManager, db_session):
        self.data_manager = data_source_manager
        self.db = db_session
    
    async def get_dcf_input_data(self, ticker: str) -> Dict:
        """Get all required data for DCF calculation"""
        # Get current price and market data
        price_data = await self.data_manager.get_stock_data(ticker, 'price')
        if not price_data:
            raise ValueError(f"Could not fetch price data for {ticker}")
        
        # Get financial statements
        financial_data = await self.data_manager.get_stock_data(ticker, 'financials')
        if not financial_data:
            raise ValueError(f"Could not fetch financial data for {ticker}")
        
        # Transform data for DCF module
        dcf_data = {
            'ticker': ticker,
            'current_price': price_data.get('current_price'),
            'shares_outstanding': financial_data['company_info'].get('shares_outstanding'),
            'market_cap': financial_data['company_info'].get('market_cap'),
            'revenue_history': self.extract_revenue_history(financial_data),
            'operating_cash_flow': self.extract_cash_flow_history(financial_data),
            'capex': self.extract_capex_history(financial_data),
            'working_capital_changes': self.extract_working_capital_changes(financial_data),
            'total_debt': self.extract_total_debt(financial_data),
            'cash_and_equivalents': self.extract_cash(financial_data),
            'beta': financial_data['company_info'].get('beta', 1.0),
            'risk_free_rate': await self.get_risk_free_rate(),
            'market_risk_premium': 0.06,  # Standard assumption
            'tax_rate': self.calculate_effective_tax_rate(financial_data)
        }
        
        # Validate data completeness
        quality_score = self.assess_data_quality(dcf_data)
        dcf_data['quality_score'] = quality_score
        
        return dcf_data
    
    def extract_revenue_history(self, financial_data: Dict) -> List[float]:
        """Extract 5-year revenue history from financial statements"""
        income_statements = financial_data.get('income_statements', [])
        revenues = []
        
        for statement in sorted(income_statements, key=lambda x: x.get('fiscal_year', 0)):
            revenue = statement.get('data', {}).get('total_revenue') or statement.get('data', {}).get('revenue')
            if revenue:
                revenues.append(float(revenue))
        
        return revenues[-5:]  # Last 5 years
    
    def assess_data_quality(self, dcf_data: Dict) -> float:
        """Assess quality of data for DCF calculation"""
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
```

### Frontend Setup
1. **Install Dependencies**:
```bash
cd frontend
npm install axios swr
```

2. **Create Data Service**:
```typescript
// frontend/src/services/dataService.ts
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface StockPrice {
  current_price: number;
  volume: number;
  high: number;
  low: number;
  open: number;
}

export interface DCFInputData {
  ticker: string;
  current_price: number;
  shares_outstanding: number;
  revenue_history: number[];
  operating_cash_flow: number[];
  quality_score: number;
}

class DataService {
  private api = axios.create({
    baseURL: `${API_BASE_URL}/api/v1/data`,
    timeout: 30000,
  });

  constructor() {
    // Add auth token to requests
    this.api.interceptors.request.use((config) => {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  async getCurrentPrice(ticker: string): Promise<StockPrice> {
    const response = await this.api.get(`/stock/${ticker}/price`);
    return response.data;
  }

  async getDCFData(ticker: string): Promise<DCFInputData> {
    const response = await this.api.get(`/stock/${ticker}/dcf-data`);
    return response.data;
  }

  async getHistoricalPrices(ticker: string, startDate: string, endDate: string) {
    const response = await this.api.get(`/stock/${ticker}/historical`, {
      params: { start_date: startDate, end_date: endDate }
    });
    return response.data;
  }

  async getDataQuality(ticker: string) {
    const response = await this.api.get(`/data-quality/${ticker}`);
    return response.data;
  }
}

export const dataService = new DataService();
```

## 🧪 Testing Setup

### Backend Tests
**Location**: `backend/tests/test_data.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.api.data.sources import DataSourceManager
from app.api.data.services import FinancialDataService

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
        test_data = {"current_price": 150.0, "volume": 1000000}
        await manager.cache_data("AAPL", "price", test_data)
        
        redis_mock.setex.assert_called_once()
        
        # Test cache retrieval
        redis_mock.get.return_value = '{"current_price": 150.0, "volume": 1000000}'
        cached = await manager.get_cached_data("AAPL", "price")
        
        assert cached["current_price"] == 150.0

class TestFinancialDataService:
    @pytest.mark.asyncio
    async def test_dcf_data_extraction(self):
        mock_manager = AsyncMock()
        mock_manager.get_stock_data.side_effect = [
            {"current_price": 150.0},  # price data
            {  # financial data
                "company_info": {
                    "shares_outstanding": 1000000,
                    "market_cap": 150000000,
                    "beta": 1.2
                },
                "income_statements": [
                    {"fiscal_year": 2023, "data": {"total_revenue": 1000000}},
                    {"fiscal_year": 2022, "data": {"total_revenue": 950000}}
                ],
                "cash_flow_statements": [
                    {"fiscal_year": 2023, "data": {"operating_cash_flow": 200000}},
                    {"fiscal_year": 2022, "data": {"operating_cash_flow": 180000}}
                ]
            }
        ]
        
        service = FinancialDataService(mock_manager, Mock())
        
        # Mock additional methods
        service.extract_cash_flow_history = Mock(return_value=[180000, 200000])
        service.extract_capex_history = Mock(return_value=[50000, 55000])
        service.extract_working_capital_changes = Mock(return_value=[10000, 12000])
        service.extract_total_debt = Mock(return_value=500000)
        service.extract_cash = Mock(return_value=100000)
        service.get_risk_free_rate = AsyncMock(return_value=0.03)
        service.calculate_effective_tax_rate = Mock(return_value=0.25)
        
        dcf_data = await service.get_dcf_input_data("AAPL")
        
        assert dcf_data["ticker"] == "AAPL"
        assert dcf_data["current_price"] == 150.0
        assert len(dcf_data["revenue_history"]) == 2
```

## 📚 Integration Points

### Services Provided to Other Modules
```python
# Primary interface for other modules
class DataInterface:
    async def get_financial_data_for_dcf(self, ticker: str) -> Dict:
        """Primary interface for DCF Module"""
        pass
    
    async def get_current_stock_price(self, ticker: str) -> float:
        """Interface for Portfolio Module"""
        pass
    
    async def validate_ticker(self, ticker: str) -> bool:
        """Validate if ticker exists and has data"""
        pass
```

### API Endpoints to Implement
```
GET  /api/v1/data/stock/{ticker}/price           # Current stock price
GET  /api/v1/data/stock/{ticker}/dcf-data        # DCF input data
GET  /api/v1/data/stock/{ticker}/historical      # Historical prices
GET  /api/v1/data/data-quality/{ticker}          # Data quality score
GET  /api/v1/data/search/{query}                 # Search stocks
POST /api/v1/data/validate-ticker                # Validate ticker
```

## 📋 Checklist
- [ ] Set up Redis connection and caching
- [ ] Create database models for financial data
- [ ] Implement Yahoo Finance API integration
- [ ] Implement Alpha Vantage API integration
- [ ] Create rate limiting system
- [ ] Implement data quality assessment
- [ ] Create API endpoints for data fetching
- [ ] Build frontend data service
- [ ] Add comprehensive error handling
- [ ] Write unit tests for data sources
- [ ] Write integration tests for API endpoints
- [ ] Test rate limiting functionality
- [ ] Update main.py to include data router
- [ ] Test integration with DCF Module

## 🚨 Important Notes
- **API Keys**: Secure storage of API keys in environment variables
- **Rate Limiting**: Respect external API rate limits to avoid blocking
- **Data Quality**: Implement robust data validation and quality scoring
- **Caching**: Use appropriate TTL values for different data types
- **Error Handling**: Graceful fallback between data sources
- **Performance**: Optimize for concurrent requests and caching
- **Monitoring**: Log all API calls for debugging and monitoring

## 📞 Need Help?
- Check `DATA_MODULE_CLAUDE.md` for detailed specifications
- Review external API documentation (Yahoo Finance, Alpha Vantage)
- Test API endpoints using `/docs` (FastAPI auto-docs)
- Monitor Redis cache usage and performance
- Validate data quality scores with sample stocks