# DCF Module - Development Setup Guide

## 📋 Module Overview
**Responsibility**: Core DCF (Discounted Cash Flow) calculation engine with multi-scenario modeling, sensitivity analysis, and comprehensive valuation metrics.

## 🎯 What's Already Set Up
- ✅ Project structure with backend/frontend folders
- ✅ FastAPI main application (`backend/main.py`)
- ✅ Next.js configuration
- ✅ Docker configuration
- ✅ Database structure defined
- ✅ Module specification (`DCF_MODULE_CLAUDE.md`)

## 🚀 Your Development Tasks

### 1. Backend Implementation
**Location**: `backend/app/api/dcf/`

**Files to Create**:
```
backend/app/api/dcf/
├── __init__.py
├── routes.py          # DCF analysis endpoints
├── schemas.py         # Pydantic models for DCF data
├── services.py        # DCF business logic
└── engine.py          # Core DCF calculation engine
```

**Key Components to Implement**:
- `DCFCalculationEngine` class (from specification)
- `DCFService` class for API integration
- Multi-scenario analysis (worst/base/best case)
- Sensitivity analysis matrix generation
- WACC calculation
- Terminal value calculations

### 2. Database Models
**Location**: `backend/app/models/`

**Files to Create**:
```
backend/app/models/
├── dcf.py             # DCF calculation models
└── analysis.py        # Analysis result models
```

**Models to Implement**:
- `DCFCalculation` model
- `DCFAssumptions` model
- `SensitivityAnalysis` model
- `ScenarioResult` model

### 3. Frontend Components
**Location**: `frontend/src/components/dcf/`

**Components to Create**:
```
frontend/src/components/dcf/
├── DCFAnalysisForm.tsx
├── ScenarioComparison.tsx
├── SensitivityMatrix.tsx
├── AssumptionsPanel.tsx
├── DCFResults.tsx
├── IntrinsicValueCard.tsx
└── DCFHistory.tsx
```

## 🔧 Development Environment Setup

### Backend Setup
1. **Install Additional Dependencies**:
```bash
cd backend
pip install numpy pandas scipy yfinance alpha-vantage python-dateutil
```

2. **Create Database Models**:
```python
# backend/app/models/dcf.py
from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class DCFCalculation(Base):
    __tablename__ = "dcf_calculations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticker = Column(String(10), nullable=False, index=True)
    calculation_date = Column(DateTime(timezone=True), server_default=func.now())
    input_data = Column(JSONB, nullable=False)
    scenario_results = Column(JSONB, nullable=False)
    sensitivity_data = Column(JSONB)
    quality_score = Column(DECIMAL(3,2))
    calculation_version = Column(String(10), default='1.0')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    assumptions = relationship("DCFAssumptions", back_populates="calculation", cascade="all, delete-orphan")
    sensitivity_analyses = relationship("SensitivityAnalysis", back_populates="calculation", cascade="all, delete-orphan")

class DCFAssumptions(Base):
    __tablename__ = "dcf_assumptions"
    
    id = Column(Integer, primary_key=True, index=True)
    calculation_id = Column(Integer, ForeignKey("dcf_calculations.id", ondelete="CASCADE"), nullable=False)
    scenario_type = Column(String(20), nullable=False)
    revenue_growth_rate = Column(DECIMAL(5,4))
    margin_adjustment = Column(DECIMAL(5,4))
    discount_rate = Column(DECIMAL(5,4))
    terminal_growth_rate = Column(DECIMAL(5,4))
    projection_years = Column(Integer, default=5)
    confidence_level = Column(DECIMAL(3,2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    calculation = relationship("DCFCalculation", back_populates="assumptions")
```

3. **Create DCF Calculation Engine**:
```python
# backend/app/api/dcf/engine.py
from typing import Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime
from pydantic import BaseModel

class DCFInputData(BaseModel):
    ticker: str
    current_price: float
    shares_outstanding: float
    revenue_history: List[float]
    operating_cash_flow: List[float]
    capex: List[float]
    working_capital_changes: List[float]
    total_debt: float
    cash_and_equivalents: float
    market_cap: float
    beta: float
    risk_free_rate: float
    market_risk_premium: float
    tax_rate: float

class ScenarioParameters(BaseModel):
    revenue_growth_rate: float
    margin_adjustment: float
    discount_rate: float
    terminal_growth_rate: float
    confidence_level: float
    projection_years: int = 5

class DCFScenarioResult(BaseModel):
    scenario_name: str
    intrinsic_value_per_share: float
    total_enterprise_value: float
    terminal_value: float
    projected_cash_flows: List[float]
    present_values: List[float]
    discount_rate: float
    terminal_growth_rate: float
    upside_downside_percentage: float
    assumptions: ScenarioParameters

class DCFCalculationEngine:
    def __init__(self):
        self.scenario_parameters = {
            'worst_case': ScenarioParameters(
                revenue_growth_rate=0.02,
                margin_adjustment=0.95,
                discount_rate=0.12,
                terminal_growth_rate=0.015,
                confidence_level=0.8
            ),
            'base_case': ScenarioParameters(
                revenue_growth_rate=0.05,
                margin_adjustment=1.0,
                discount_rate=0.10,
                terminal_growth_rate=0.025,
                confidence_level=0.9
            ),
            'best_case': ScenarioParameters(
                revenue_growth_rate=0.08,
                margin_adjustment=1.05,
                discount_rate=0.08,
                terminal_growth_rate=0.035,
                confidence_level=0.95
            )
        }
    
    async def calculate_comprehensive_dcf(self, input_data: DCFInputData) -> Dict:
        """Perform complete DCF analysis across all scenarios"""
        
        # 1. Validate input data quality
        quality_score = self.calculate_data_quality_score(input_data)
        
        # 2. Calculate WACC for base case
        base_wacc = self.calculate_wacc(input_data)
        
        # 3. Run DCF for each scenario
        scenario_results = {}
        for scenario_name, parameters in self.scenario_parameters.items():
            # Adjust WACC based on scenario
            adjusted_wacc = self.adjust_wacc_for_scenario(base_wacc, scenario_name)
            parameters.discount_rate = adjusted_wacc
            
            scenario_result = await self.calculate_scenario_dcf(input_data, parameters, scenario_name)
            scenario_results[scenario_name] = scenario_result
        
        # 4. Generate sensitivity analysis
        sensitivity_analysis = self.generate_sensitivity_analysis(
            input_data, scenario_results['base_case']
        )
        
        return {
            "ticker": input_data.ticker,
            "current_market_price": input_data.current_price,
            "scenarios": scenario_results,
            "sensitivity_analysis": sensitivity_analysis,
            "quality_score": quality_score,
            "calculation_timestamp": datetime.utcnow(),
            "data_freshness_score": self.calculate_data_freshness(input_data)
        }
    
    async def calculate_scenario_dcf(self, input_data: DCFInputData, 
                                   parameters: ScenarioParameters, 
                                   scenario_name: str) -> DCFScenarioResult:
        """Calculate DCF for a specific scenario"""
        
        # 1. Project future revenues
        projected_revenues = self.project_revenues(input_data, parameters)
        
        # 2. Calculate projected free cash flows
        projected_fcf = self.calculate_projected_fcf(
            input_data, projected_revenues, parameters
        )
        
        # 3. Calculate terminal value
        terminal_value = self.calculate_terminal_value(
            projected_fcf[-1], parameters.terminal_growth_rate, parameters.discount_rate
        )
        
        # 4. Discount to present value
        present_values = self.discount_to_present_value(
            projected_fcf, terminal_value, parameters.discount_rate
        )
        
        # 5. Calculate enterprise value and per-share value
        total_pv = sum(present_values)
        equity_value = total_pv - input_data.total_debt + input_data.cash_and_equivalents
        intrinsic_value_per_share = equity_value / input_data.shares_outstanding
        
        # 6. Calculate upside/downside
        upside_downside = ((intrinsic_value_per_share - input_data.current_price) / 
                          input_data.current_price) * 100
        
        return DCFScenarioResult(
            scenario_name=scenario_name,
            intrinsic_value_per_share=intrinsic_value_per_share,
            total_enterprise_value=total_pv,
            terminal_value=terminal_value,
            projected_cash_flows=projected_fcf,
            present_values=present_values,
            discount_rate=parameters.discount_rate,
            terminal_growth_rate=parameters.terminal_growth_rate,
            upside_downside_percentage=upside_downside,
            assumptions=parameters
        )
    
    def calculate_wacc(self, input_data: DCFInputData) -> float:
        """Calculate Weighted Average Cost of Capital"""
        # Cost of equity using CAPM
        cost_of_equity = (input_data.risk_free_rate + 
                         input_data.beta * input_data.market_risk_premium)
        
        # Assume cost of debt (simplified)
        cost_of_debt = input_data.risk_free_rate + 0.02  # Risk-free rate + 2% spread
        
        # Market values
        market_value_equity = input_data.market_cap
        market_value_debt = input_data.total_debt
        total_value = market_value_equity + market_value_debt
        
        if total_value == 0:
            return cost_of_equity
        
        equity_weight = market_value_equity / total_value
        debt_weight = market_value_debt / total_value
        
        wacc = (equity_weight * cost_of_equity + 
                debt_weight * cost_of_debt * (1 - input_data.tax_rate))
        
        return wacc
    
    def project_revenues(self, input_data: DCFInputData, 
                        parameters: ScenarioParameters) -> List[float]:
        """Project future revenues based on historical data and scenario parameters"""
        revenues = input_data.revenue_history
        historical_growth_rates = []
        
        for i in range(1, len(revenues)):
            growth_rate = (revenues[i] - revenues[i-1]) / revenues[i-1]
            historical_growth_rates.append(growth_rate)
        
        # Use weighted average of historical and scenario growth rates
        avg_historical_growth = np.mean(historical_growth_rates)
        blended_growth_rate = (0.3 * avg_historical_growth + 
                              0.7 * parameters.revenue_growth_rate)
        
        # Project revenues with declining growth rate
        projected_revenues = []
        last_revenue = revenues[-1]
        
        for year in range(parameters.projection_years):
            # Gradually decline growth rate towards terminal growth
            decay_factor = 0.8 ** year
            year_growth_rate = (blended_growth_rate * decay_factor + 
                               parameters.terminal_growth_rate * (1 - decay_factor))
            
            next_revenue = last_revenue * (1 + year_growth_rate)
            projected_revenues.append(next_revenue)
            last_revenue = next_revenue
        
        return projected_revenues
    
    def calculate_terminal_value(self, final_fcf: float, 
                                terminal_growth_rate: float, 
                                discount_rate: float) -> float:
        """Calculate terminal value using Gordon Growth Model"""
        if discount_rate <= terminal_growth_rate:
            raise ValueError("Discount rate must be greater than terminal growth rate")
        
        terminal_fcf = final_fcf * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
        
        return terminal_value
    
    def calculate_data_quality_score(self, input_data: DCFInputData) -> float:
        """Calculate data quality score (0-1)"""
        score = 1.0
        
        # Check for missing or zero values
        if any(rev <= 0 for rev in input_data.revenue_history):
            score -= 0.2
        
        if any(cf <= 0 for cf in input_data.operating_cash_flow):
            score -= 0.2
        
        # Check for data consistency
        revenue_volatility = np.std(input_data.revenue_history) / np.mean(input_data.revenue_history)
        if revenue_volatility > 0.3:  # High volatility
            score -= 0.1
        
        # Check for reasonable ratios
        if input_data.market_cap <= 0 or input_data.shares_outstanding <= 0:
            score -= 0.3
        
        return max(0.0, score)
```

### Frontend Setup
1. **Install Additional Dependencies**:
```bash
cd frontend
npm install recharts plotly.js react-plotly.js @types/plotly.js
```

2. **Create DCF Components**:
```typescript
// frontend/src/components/dcf/DCFAnalysisForm.tsx
import React, { useState } from 'react';
import { useForm } from 'react-hook-form';

interface DCFFormData {
  ticker: string;
}

interface DCFResult {
  ticker: string;
  current_market_price: number;
  scenarios: {
    worst_case: ScenarioResult;
    base_case: ScenarioResult;
    best_case: ScenarioResult;
  };
  sensitivity_analysis: any;
  quality_score: number;
}

interface ScenarioResult {
  intrinsic_value_per_share: number;
  upside_downside_percentage: number;
  assumptions: any;
}

const DCFAnalysisForm: React.FC = () => {
  const [result, setResult] = useState<DCFResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { register, handleSubmit, formState: { errors } } = useForm<DCFFormData>();

  const onSubmit = async (data: DCFFormData) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/v1/dcf/analyze/${data.ticker}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error('Failed to analyze stock');
      }
      
      const dcfResult = await response.json();
      setResult(dcfResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">DCF Analysis</h1>
        
        <form onSubmit={handleSubmit(onSubmit)} className="mb-8">
          <div className="flex gap-4 items-end">
            <div className="flex-1">
              <label htmlFor="ticker" className="block text-sm font-medium text-gray-700 mb-2">
                Stock Ticker
              </label>
              <input
                {...register('ticker', { 
                  required: 'Ticker is required',
                  pattern: {
                    value: /^[A-Z]{1,5}$/,
                    message: 'Please enter a valid ticker (1-5 letters)'
                  }
                })}
                type="text"
                placeholder="e.g., AAPL"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {errors.ticker && (
                <p className="text-red-500 text-sm mt-1">{errors.ticker.message}</p>
              )}
            </div>
            
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
        </form>
        
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
            <p className="text-red-700">{error}</p>
          </div>
        )}
        
        {result && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {Object.entries(result.scenarios).map(([scenarioName, scenario]) => (
                <div key={scenarioName} className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    {scenarioName.replace('_', ' ').toUpperCase()}
                  </h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Intrinsic Value:</span>
                      <span className="text-sm font-medium">
                        ${scenario.intrinsic_value_per_share.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Current Price:</span>
                      <span className="text-sm font-medium">
                        ${result.current_market_price.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Upside/Downside:</span>
                      <span className={`text-sm font-medium ${
                        scenario.upside_downside_percentage >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {scenario.upside_downside_percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="bg-blue-50 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Analysis Quality</h3>
              <div className="flex items-center">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full" 
                    style={{ width: `${result.quality_score * 100}%` }}
                  ></div>
                </div>
                <span className="ml-3 text-sm font-medium">
                  {(result.quality_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DCFAnalysisForm;
```

## 🧪 Testing Setup

### Backend Tests
**Location**: `backend/tests/test_dcf.py`

```python
import pytest
from app.api.dcf.engine import DCFCalculationEngine, DCFInputData, ScenarioParameters

class TestDCFCalculationEngine:
    def test_wacc_calculation(self):
        engine = DCFCalculationEngine()
        
        input_data = DCFInputData(
            ticker="TEST",
            current_price=100.0,
            shares_outstanding=1000000,
            revenue_history=[1000, 1100, 1200, 1300, 1400],
            operating_cash_flow=[200, 220, 240, 260, 280],
            capex=[50, 55, 60, 65, 70],
            working_capital_changes=[10, 12, 14, 16, 18],
            total_debt=500000,
            cash_and_equivalents=100000,
            market_cap=100000000,
            beta=1.2,
            risk_free_rate=0.03,
            market_risk_premium=0.06,
            tax_rate=0.25
        )
        
        wacc = engine.calculate_wacc(input_data)
        
        assert 0.05 <= wacc <= 0.15  # Reasonable WACC range
    
    def test_terminal_value_calculation(self):
        engine = DCFCalculationEngine()
        
        terminal_value = engine.calculate_terminal_value(
            final_fcf=1000,
            terminal_growth_rate=0.025,
            discount_rate=0.10
        )
        
        expected = 1000 * 1.025 / (0.10 - 0.025)
        assert abs(terminal_value - expected) < 0.01
    
    def test_data_quality_assessment(self):
        engine = DCFCalculationEngine()
        
        # Good quality data
        good_data = DCFInputData(
            ticker="TEST",
            current_price=100.0,
            shares_outstanding=1000000,
            revenue_history=[1000, 1100, 1200, 1300, 1400],
            operating_cash_flow=[200, 220, 240, 260, 280],
            capex=[50, 55, 60, 65, 70],
            working_capital_changes=[10, 12, 14, 16, 18],
            total_debt=500000,
            cash_and_equivalents=100000,
            market_cap=100000000,
            beta=1.2,
            risk_free_rate=0.03,
            market_risk_premium=0.06,
            tax_rate=0.25
        )
        
        score = engine.calculate_data_quality_score(good_data)
        assert score >= 0.8
```

## 📚 Integration Points

### Dependencies on Other Modules
- **User Module**: Requires authentication for saving calculations
- **Data Module**: Requires financial data input for DCF calculations
- **Portfolio Module**: May save DCF results to portfolios

### Services Provided to Other Modules
```python
# Services other modules can use
class DCFInterface:
    async def get_dcf_summary(self, calculation_id: int) -> dict:
        """Provide DCF summary for other modules"""
        pass
    
    async def get_intrinsic_value(self, ticker: str) -> float:
        """Get latest intrinsic value for a ticker"""
        pass
```

### API Endpoints to Implement
```
POST /api/v1/dcf/analyze/{ticker}           # Perform DCF analysis
GET  /api/v1/dcf/analysis/{calculation_id}  # Get stored analysis
GET  /api/v1/dcf/history                    # Get user's calculation history
POST /api/v1/dcf/custom-scenario            # Custom scenario analysis
GET  /api/v1/dcf/sensitivity/{calculation_id} # Get sensitivity analysis
```

## 📋 Checklist
- [ ] Create database models for DCF calculations
- [ ] Implement DCF calculation engine with all scenarios
- [ ] Create WACC calculation logic
- [ ] Implement sensitivity analysis
- [ ] Create API endpoints for DCF analysis
- [ ] Build frontend components for DCF input and results
- [ ] Add data validation and quality scoring
- [ ] Write comprehensive unit tests for calculation engine
- [ ] Write integration tests for API endpoints
- [ ] Write frontend component tests
- [ ] Update main.py to include DCF router
- [ ] Test integration with Data Module for financial data
- [ ] Performance test for calculation speed

## 🚨 Important Notes
- Ensure calculation accuracy - financial calculations must be precise
- Add proper error handling for edge cases (negative growth rates, etc.)
- Implement input validation for all financial parameters
- Add disclaimers about DCF assumptions and limitations
- Consider implementing calculation caching for performance
- Add logging for all calculations for audit purposes
- Validate that discount rate > terminal growth rate

## 📞 Need Help?
- Check `DCF_MODULE_CLAUDE.md` for detailed specifications
- Review financial calculation formulas carefully
- Test calculations against known DCF examples
- Use `/docs` endpoint to test your API endpoints
- Validate results with financial professionals if possible