# Portfolio Module - Development Setup Guide

## 📋 Module Overview
**Responsibility**: Portfolio management, watchlists, saved DCF analyses, and investment tracking functionality.

## 🎯 What's Already Set Up
- ✅ Project structure with backend/frontend folders
- ✅ FastAPI main application (`backend/main.py`)
- ✅ Next.js configuration
- ✅ Docker configuration
- ✅ Database structure defined
- ✅ Module specification (`PORTFOLIO_MODULE_CLAUDE.md`)

## 🚀 Your Development Tasks

### 1. Backend Implementation
**Location**: `backend/app/api/portfolio/`

**Files to Create**:
```
backend/app/api/portfolio/
├── __init__.py
├── routes.py          # Portfolio and watchlist endpoints
├── schemas.py         # Pydantic models
└── services.py        # Portfolio business logic
```

**Key Components to Implement**:
- `PortfolioService` class (from specification)
- `WatchlistService` class (from specification)
- Portfolio CRUD operations
- Watchlist management
- Portfolio performance calculations

### 2. Database Models
**Location**: `backend/app/models/`

**Files to Create**:
```
backend/app/models/
├── portfolio.py       # Portfolio SQLAlchemy models
└── watchlist.py       # Watchlist SQLAlchemy models
```

**Models to Implement**:
- `Portfolio` model
- `PortfolioItem` model
- `Watchlist` model
- `WatchlistItem` model
- `SavedDCFAnalysis` model
- `PortfolioSnapshot` model

### 3. Frontend Components
**Location**: `frontend/src/components/portfolio/`

**Components to Create**:
```
frontend/src/components/portfolio/
├── PortfolioList.tsx
├── PortfolioDetails.tsx
├── PortfolioForm.tsx
├── WatchlistManager.tsx
├── WatchlistItem.tsx
├── PerformanceTracker.tsx
├── AddStockModal.tsx
└── PortfolioSummary.tsx
```

## 🔧 Development Environment Setup

### Backend Setup
1. **Install Additional Dependencies**:
```bash
cd backend
pip install pandas numpy python-dateutil
```

2. **Create Database Models**:
```python
# backend/app/models/portfolio.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, DECIMAL, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class Portfolio(Base):
    __tablename__ = "portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    items = relationship("PortfolioItem", back_populates="portfolio", cascade="all, delete-orphan")
    user = relationship("User", back_populates="portfolios")

class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(10), nullable=False)
    shares_owned = Column(DECIMAL(15,4), default=0)
    average_cost = Column(DECIMAL(10,2), default=0)
    target_allocation = Column(DECIMAL(5,2), default=0)
    notes = Column(Text)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="items")
```

3. **Create Portfolio Service**:
```python
# backend/app/api/portfolio/services.py
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.portfolio import Portfolio, PortfolioItem
from app.models.user import User

class PortfolioService:
    def __init__(self, db: Session):
        self.db = db
    
    async def create_portfolio(self, user_id: int, portfolio_data: dict) -> Portfolio:
        """Create new portfolio for user"""
        portfolio = Portfolio(
            user_id=user_id,
            name=portfolio_data["name"],
            description=portfolio_data.get("description"),
            is_public=portfolio_data.get("is_public", False)
        )
        
        self.db.add(portfolio)
        await self.db.commit()
        await self.db.refresh(portfolio)
        
        return portfolio
    
    async def get_user_portfolios(self, user_id: int) -> List[Portfolio]:
        """Get all portfolios for a user"""
        result = await self.db.execute(
            select(Portfolio).where(Portfolio.user_id == user_id)
        )
        return result.scalars().all()
    
    async def add_portfolio_item(self, portfolio_id: int, item_data: dict) -> dict:
        """Add stock to portfolio"""
        # Check if item already exists
        existing_item = await self.db.execute(
            select(PortfolioItem).where(
                PortfolioItem.portfolio_id == portfolio_id,
                PortfolioItem.ticker == item_data["ticker"]
            )
        )
        existing = existing_item.scalar_one_or_none()
        
        if existing:
            # Update existing item
            existing.shares_owned += item_data["shares_owned"]
            existing.average_cost = self.calculate_average_cost(
                existing.shares_owned, existing.average_cost,
                item_data["shares_owned"], item_data["average_cost"]
            )
            await self.db.commit()
            return {"message": "Portfolio item updated", "item_id": existing.id}
        else:
            # Create new item
            portfolio_item = PortfolioItem(
                portfolio_id=portfolio_id,
                ticker=item_data["ticker"],
                shares_owned=item_data["shares_owned"],
                average_cost=item_data["average_cost"],
                target_allocation=item_data.get("target_allocation", 0),
                notes=item_data.get("notes")
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

### Frontend Setup
1. **Install Additional Dependencies**:
```bash
cd frontend
npm install react-table @types/react-table react-select date-fns
```

2. **Create Portfolio Components**:
```typescript
// frontend/src/components/portfolio/PortfolioList.tsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../auth/AuthProvider';

interface Portfolio {
  id: number;
  name: string;
  description?: string;
  total_value?: number;
  total_cost?: number;
  unrealized_gain_loss?: number;
  item_count: number;
  created_at: string;
  updated_at: string;
}

const PortfolioList: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const fetchPortfolios = async () => {
    try {
      const response = await fetch('/api/v1/portfolios/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        setPortfolios(data);
      }
    } catch (error) {
      console.error('Error fetching portfolios:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="animate-pulse">Loading portfolios...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">My Portfolios</h1>
        <button className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
          Create Portfolio
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {portfolios.map((portfolio) => (
          <div key={portfolio.id} className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold text-gray-900">{portfolio.name}</h3>
            {portfolio.description && (
              <p className="text-gray-600 mt-2">{portfolio.description}</p>
            )}
            
            <div className="mt-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Total Value:</span>
                <span className="text-sm font-medium">
                  ${portfolio.total_value?.toLocaleString() || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Holdings:</span>
                <span className="text-sm font-medium">{portfolio.item_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">P&L:</span>
                <span className={`text-sm font-medium ${
                  (portfolio.unrealized_gain_loss || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  ${portfolio.unrealized_gain_loss?.toLocaleString() || 'N/A'}
                </span>
              </div>
            </div>
            
            <div className="mt-4 flex space-x-2">
              <button className="flex-1 bg-gray-100 text-gray-700 px-3 py-2 rounded text-sm hover:bg-gray-200">
                View
              </button>
              <button className="flex-1 bg-blue-100 text-blue-700 px-3 py-2 rounded text-sm hover:bg-blue-200">
                Edit
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PortfolioList;
```

## 🧪 Testing Setup

### Backend Tests
**Location**: `backend/tests/test_portfolio.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_portfolio():
    # First login to get token
    login_response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Create portfolio
    response = client.post("/api/v1/portfolios/", 
        json={
            "name": "My Investment Portfolio",
            "description": "Long-term growth portfolio"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My Investment Portfolio"
    assert "id" in data

def test_add_portfolio_item():
    # Setup: Create portfolio and get ID
    # ... (portfolio creation code)
    
    response = client.post(f"/api/v1/portfolios/{portfolio_id}/items",
        json={
            "ticker": "AAPL",
            "shares_owned": 100,
            "average_cost": 150.50
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert "item_id" in response.json()
```

### Frontend Tests
**Location**: `frontend/src/components/portfolio/__tests__/PortfolioList.test.tsx`

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import PortfolioList from '../PortfolioList';
import { AuthProvider } from '../../auth/AuthProvider';

// Mock fetch
global.fetch = jest.fn();

test('renders portfolio list', async () => {
  (fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => ([
      {
        id: 1,
        name: "Test Portfolio",
        description: "Test Description",
        total_value: 10000,
        item_count: 5
      }
    ])
  });

  render(
    <AuthProvider>
      <PortfolioList />
    </AuthProvider>
  );

  await waitFor(() => {
    expect(screen.getByText('Test Portfolio')).toBeInTheDocument();
    expect(screen.getByText('Test Description')).toBeInTheDocument();
  });
});
```

## 📚 Integration Points

### Dependencies on Other Modules
- **User Module**: Requires `get_current_user` dependency for authentication
- **Data Module**: May call data service for real-time stock prices
- **DCF Module**: Integration for saving DCF analyses to portfolios

### Services Provided to Other Modules
```python
# Services other modules can use
class PortfolioInterface:
    async def get_user_portfolio_tickers(self, user_id: int) -> List[str]:
        """Get all tickers in user's portfolios"""
        pass
    
    async def save_dcf_to_portfolio(self, user_id: int, portfolio_id: int, 
                                   dcf_data: dict) -> int:
        """Save DCF analysis to portfolio"""
        pass
```

### API Endpoints to Implement
```
POST /api/v1/portfolios/                    # Create portfolio
GET  /api/v1/portfolios/                    # Get user portfolios
GET  /api/v1/portfolios/{id}                # Get portfolio details
PUT  /api/v1/portfolios/{id}                # Update portfolio
DELETE /api/v1/portfolios/{id}              # Delete portfolio
POST /api/v1/portfolios/{id}/items          # Add item to portfolio
PUT  /api/v1/portfolios/{id}/items/{item_id} # Update portfolio item
DELETE /api/v1/portfolios/{id}/items/{item_id} # Remove item

POST /api/v1/watchlists/                    # Create watchlist
GET  /api/v1/watchlists/                    # Get user watchlists
POST /api/v1/watchlists/{id}/items          # Add to watchlist
DELETE /api/v1/watchlists/{id}/items/{item_id} # Remove from watchlist
```

## 📋 Checklist
- [ ] Create database models (Portfolio, PortfolioItem, Watchlist, etc.)
- [ ] Implement portfolio service with CRUD operations
- [ ] Implement watchlist service
- [ ] Create API endpoints for portfolio management
- [ ] Build frontend components (PortfolioList, PortfolioDetails, etc.)
- [ ] Implement portfolio performance calculations
- [ ] Add real-time price integration (optional)
- [ ] Write unit tests for services
- [ ] Write integration tests for API endpoints
- [ ] Write frontend component tests
- [ ] Update main.py to include portfolio router
- [ ] Test integration with User Module authentication

## 🚨 Important Notes
- Ensure proper user authorization (users can only access their own portfolios)
- Implement portfolio sharing functionality if `is_public` is true
- Add data validation for stock tickers
- Consider implementing portfolio rebalancing calculations
- Add proper error handling for invalid tickers
- Implement soft delete for portfolios (for data recovery)

## 📞 Need Help?
- Check `PORTFOLIO_MODULE_CLAUDE.md` for detailed specifications
- Review User Module setup for authentication integration
- Use `/docs` endpoint to test your API endpoints
- Check the main project documentation for database setup