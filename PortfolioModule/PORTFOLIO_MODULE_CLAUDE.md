# Portfolio Module - Technical Specification

## 📋 Module Overview
**Purpose**: Manage user portfolios, watchlists, saved DCF analyses, and investment tracking functionality.

**Core Responsibility**: Provide portfolio management services that allow users to organize, track, and manage their investment analyses and watchlists.

## 🎯 Module Scope & Boundaries

### ✅ What This Module Handles:
- Portfolio creation and management
- Watchlist functionality
- Saved DCF analysis tracking
- Portfolio performance monitoring
- Investment position tracking
- Portfolio sharing and collaboration
- Historical portfolio data

### ❌ What This Module Does NOT Handle:
- User authentication (handled by User Module)
- DCF calculations (handled by DCF Module)
- Financial data fetching (handled by Data Module)
- Chart generation (handled by Report Module)

## 🏗️ Technical Architecture

### Database Schema
```sql
-- Portfolio containers
CREATE TABLE portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Portfolio items (stocks in portfolio)
CREATE TABLE portfolio_items (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    shares_owned DECIMAL(15,4) DEFAULT 0,
    average_cost DECIMAL(10,2) DEFAULT 0,
    target_allocation DECIMAL(5,2) DEFAULT 0,
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Watchlist functionality
CREATE TABLE watchlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL DEFAULT 'My Watchlist',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Watchlist items
CREATE TABLE watchlist_items (
    id SERIAL PRIMARY KEY,
    watchlist_id INTEGER REFERENCES watchlists(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    target_price DECIMAL(10,2),
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(watchlist_id, ticker)
);

-- Saved DCF analyses
CREATE TABLE saved_dcf_analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE SET NULL,
    ticker VARCHAR(10) NOT NULL,
    analysis_name VARCHAR(255),
    dcf_data JSONB NOT NULL,
    scenario_results JSONB NOT NULL,
    market_price_at_save DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Portfolio performance tracking
CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
    total_value DECIMAL(15,2),
    total_cost DECIMAL(15,2),
    unrealized_gain_loss DECIMAL(15,2),
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Core Classes & Services

#### Portfolio Service
```python
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date

class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False

class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None

class PortfolioItemCreate(BaseModel):
    ticker: str
    shares_owned: float = 0
    average_cost: float = 0
    target_allocation: float = 0
    notes: Optional[str] = None

class PortfolioResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_public: bool
    total_value: Optional[float]
    total_cost: Optional[float]
    unrealized_gain_loss: Optional[float]
    item_count: int
    created_at: datetime
    updated_at: datetime

class PortfolioService:
    def __init__(self, db_session):
        self.db = db_session
    
    async def create_portfolio(self, user_id: int, portfolio_data: PortfolioCreate) -> PortfolioResponse:
        """Create new portfolio for user"""
        portfolio = Portfolio(
            user_id=user_id,
            name=portfolio_data.name,
            description=portfolio_data.description,
            is_public=portfolio_data.is_public
        )
        
        self.db.add(portfolio)
        await self.db.commit()
        await self.db.refresh(portfolio)
        
        return await self.get_portfolio_with_stats(portfolio.id)
    
    async def get_user_portfolios(self, user_id: int) -> List[PortfolioResponse]:
        """Get all portfolios for a user"""
        result = await self.db.execute(
            select(Portfolio).where(Portfolio.user_id == user_id)
        )
        portfolios = result.scalars().all()
        
        portfolio_responses = []
        for portfolio in portfolios:
            portfolio_response = await self.get_portfolio_with_stats(portfolio.id)
            portfolio_responses.append(portfolio_response)
        
        return portfolio_responses
    
    async def get_portfolio_with_stats(self, portfolio_id: int) -> PortfolioResponse:
        """Get portfolio with calculated statistics"""
        portfolio = await self.db.get(Portfolio, portfolio_id)
        if not portfolio:
            raise ValueError("Portfolio not found")
        
        # Calculate portfolio statistics
        stats = await self.calculate_portfolio_stats(portfolio_id)
        
        return PortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            is_public=portfolio.is_public,
            total_value=stats.get('total_value'),
            total_cost=stats.get('total_cost'),
            unrealized_gain_loss=stats.get('unrealized_gain_loss'),
            item_count=stats.get('item_count', 0),
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at
        )
    
    async def add_portfolio_item(self, portfolio_id: int, item_data: PortfolioItemCreate) -> dict:
        """Add stock to portfolio"""
        # Check if item already exists
        existing_item = await self.db.execute(
            select(PortfolioItem).where(
                PortfolioItem.portfolio_id == portfolio_id,
                PortfolioItem.ticker == item_data.ticker
            )
        )
        existing = existing_item.scalar_one_or_none()
        
        if existing:
            # Update existing item
            existing.shares_owned += item_data.shares_owned
            existing.average_cost = self.calculate_average_cost(
                existing.shares_owned, existing.average_cost,
                item_data.shares_owned, item_data.average_cost
            )
            existing.updated_at = datetime.utcnow()
            await self.db.commit()
            return {"message": "Portfolio item updated", "item_id": existing.id}
        else:
            # Create new item
            portfolio_item = PortfolioItem(
                portfolio_id=portfolio_id,
                ticker=item_data.ticker,
                shares_owned=item_data.shares_owned,
                average_cost=item_data.average_cost,
                target_allocation=item_data.target_allocation,
                notes=item_data.notes
            )
            
            self.db.add(portfolio_item)
            await self.db.commit()
            await self.db.refresh(portfolio_item)
            
            return {"message": "Portfolio item added", "item_id": portfolio_item.id}
    
    def calculate_average_cost(self, existing_shares: float, existing_cost: float, 
                             new_shares: float, new_cost: float) -> float:
        """Calculate weighted average cost"""
        if existing_shares + new_shares == 0:
            return 0
        
        total_cost = (existing_shares * existing_cost) + (new_shares * new_cost)
        total_shares = existing_shares + new_shares
        return total_cost / total_shares
```

#### Watchlist Service
```python
class WatchlistCreate(BaseModel):
    name: str = "My Watchlist"
    description: Optional[str] = None

class WatchlistItemCreate(BaseModel):
    ticker: str
    target_price: Optional[float] = None
    notes: Optional[str] = None

class WatchlistService:
    def __init__(self, db_session):
        self.db = db_session
    
    async def create_watchlist(self, user_id: int, watchlist_data: WatchlistCreate) -> dict:
        """Create new watchlist for user"""
        watchlist = Watchlist(
            user_id=user_id,
            name=watchlist_data.name,
            description=watchlist_data.description
        )
        
        self.db.add(watchlist)
        await self.db.commit()
        await self.db.refresh(watchlist)
        
        return {
            "id": watchlist.id,
            "name": watchlist.name,
            "description": watchlist.description,
            "created_at": watchlist.created_at
        }
    
    async def add_to_watchlist(self, watchlist_id: int, item_data: WatchlistItemCreate) -> dict:
        """Add stock to watchlist"""
        try:
            watchlist_item = WatchlistItem(
                watchlist_id=watchlist_id,
                ticker=item_data.ticker,
                target_price=item_data.target_price,
                notes=item_data.notes
            )
            
            self.db.add(watchlist_item)
            await self.db.commit()
            await self.db.refresh(watchlist_item)
            
            return {
                "message": "Stock added to watchlist",
                "item_id": watchlist_item.id,
                "ticker": watchlist_item.ticker
            }
        except IntegrityError:
            raise ValueError(f"Stock {item_data.ticker} is already in this watchlist")
    
    async def get_user_watchlists(self, user_id: int) -> List[dict]:
        """Get all watchlists for a user with items"""
        result = await self.db.execute(
            select(Watchlist).where(Watchlist.user_id == user_id)
        )
        watchlists = result.scalars().all()
        
        watchlist_data = []
        for watchlist in watchlists:
            items = await self.get_watchlist_items(watchlist.id)
            watchlist_data.append({
                "id": watchlist.id,
                "name": watchlist.name,
                "description": watchlist.description,
                "item_count": len(items),
                "items": items,
                "created_at": watchlist.created_at
            })
        
        return watchlist_data
```

## 🔌 API Endpoints

### Portfolio Management
```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1/portfolios", tags=["portfolios"])

@router.post("/", response_model=PortfolioResponse)
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    current_user_id: int = Depends(get_user_id),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Create new portfolio"""
    return await portfolio_service.create_portfolio(current_user_id, portfolio_data)

@router.get("/", response_model=List[PortfolioResponse])
async def get_user_portfolios(
    current_user_id: int = Depends(get_user_id),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Get all portfolios for current user"""
    return await portfolio_service.get_user_portfolios(current_user_id)

@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: int,
    current_user_id: int = Depends(get_user_id),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Get specific portfolio with details"""
    portfolio = await portfolio_service.get_portfolio_with_stats(portfolio_id)
    
    # Verify ownership or public access
    if portfolio.user_id != current_user_id and not portfolio.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this portfolio"
        )
    
    return portfolio

@router.post("/{portfolio_id}/items")
async def add_portfolio_item(
    portfolio_id: int,
    item_data: PortfolioItemCreate,
    current_user_id: int = Depends(get_user_id),
    portfolio_service: PortfolioService = Depends(get_portfolio_service)
):
    """Add stock to portfolio"""
    # Verify portfolio ownership
    await portfolio_service.verify_portfolio_ownership(portfolio_id, current_user_id)
    
    return await portfolio_service.add_portfolio_item(portfolio_id, item_data)
```

### Watchlist Management
```python
@router.post("/watchlists/")
async def create_watchlist(
    watchlist_data: WatchlistCreate,
    current_user_id: int = Depends(get_user_id),
    watchlist_service: WatchlistService = Depends(get_watchlist_service)
):
    """Create new watchlist"""
    return await watchlist_service.create_watchlist(current_user_id, watchlist_data)

@router.get("/watchlists/")
async def get_user_watchlists(
    current_user_id: int = Depends(get_user_id),
    watchlist_service: WatchlistService = Depends(get_watchlist_service)
):
    """Get all watchlists for current user"""
    return await watchlist_service.get_user_watchlists(current_user_id)

@router.post("/watchlists/{watchlist_id}/items")
async def add_to_watchlist(
    watchlist_id: int,
    item_data: WatchlistItemCreate,
    current_user_id: int = Depends(get_user_id),
    watchlist_service: WatchlistService = Depends(get_watchlist_service)
):
    """Add stock to watchlist"""
    # Verify watchlist ownership
    await watchlist_service.verify_watchlist_ownership(watchlist_id, current_user_id)
    
    return await watchlist_service.add_to_watchlist(watchlist_id, item_data)
```

## 🔗 Module Interfaces

### Outgoing Dependencies
```python
# User Module - for authentication
from user_module import get_user_id, get_current_user

# Data Module - for real-time stock prices (optional)
async def get_current_stock_price(ticker: str) -> float:
    """Get current stock price for portfolio valuation"""
    # This would call the Data Module's price service
    pass

# DCF Module - for linking saved analyses
async def get_dcf_analysis_summary(analysis_id: int) -> dict:
    """Get DCF analysis summary for portfolio context"""
    # This would call the DCF Module's analysis service
    pass
```

### Incoming Dependencies
```python
# Services provided to other modules
class PortfolioInterface:
    async def get_user_portfolio_tickers(self, user_id: int) -> List[str]:
        """Get all tickers in user's portfolios for other modules"""
        pass
    
    async def save_dcf_to_portfolio(self, user_id: int, portfolio_id: int, 
                                   dcf_data: dict) -> int:
        """Save DCF analysis to portfolio"""
        pass
    
    async def get_portfolio_context_for_reports(self, portfolio_id: int) -> dict:
        """Provide portfolio context for report generation"""
        pass
```

## 🧪 Testing Strategy

### Unit Tests
```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestPortfolioService:
    @pytest.mark.asyncio
    async def test_create_portfolio(self):
        mock_db = AsyncMock()
        portfolio_service = PortfolioService(mock_db)
        
        portfolio_data = PortfolioCreate(
            name="Test Portfolio",
            description="Test Description"
        )
        
        result = await portfolio_service.create_portfolio(1, portfolio_data)
        assert result.name == "Test Portfolio"
        assert result.description == "Test Description"
    
    def test_calculate_average_cost(self):
        portfolio_service = PortfolioService(Mock())
        
        # Test weighted average calculation
        avg_cost = portfolio_service.calculate_average_cost(
            existing_shares=100, existing_cost=50.0,
            new_shares=50, new_cost=60.0
        )
        
        expected = ((100 * 50.0) + (50 * 60.0)) / 150
        assert avg_cost == expected
```

### Integration Tests
```python
class TestPortfolioEndpoints:
    def test_create_portfolio(self, authenticated_client):
        response = authenticated_client.post("/api/v1/portfolios/", json={
            "name": "My Investment Portfolio",
            "description": "Long-term growth portfolio"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Investment Portfolio"
        assert "id" in data
    
    def test_add_portfolio_item(self, authenticated_client, portfolio_id):
        response = authenticated_client.post(
            f"/api/v1/portfolios/{portfolio_id}/items",
            json={
                "ticker": "AAPL",
                "shares_owned": 100,
                "average_cost": 150.50
            }
        )
        
        assert response.status_code == 200
        assert "item_id" in response.json()
```

## 📊 Performance Requirements

### Response Times
- Portfolio listing: < 200ms
- Portfolio details: < 300ms
- Add/update items: < 150ms

### Scalability
- Support 10,000+ portfolios per user
- Efficient pagination for large portfolios
- Optimized queries for portfolio statistics

## 🚀 Deployment Considerations

### Caching Strategy
- Cache portfolio statistics for 5 minutes
- Cache watchlist data for 2 minutes
- Invalidate cache on portfolio updates

### Data Retention
- Keep portfolio snapshots for 2 years
- Archive old portfolio versions
- Soft delete for user data recovery

---

This module provides comprehensive portfolio management functionality while maintaining clear boundaries with other system components.