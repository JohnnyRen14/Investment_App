# DCF Module - Technical Specification

## 📋 Module Overview
**Purpose**: Core DCF (Discounted Cash Flow) calculation engine that performs sophisticated multi-scenario valuation analysis with sensitivity testing.

**Core Responsibility**: Provide accurate, professional-grade DCF calculations with multiple scenarios, sensitivity analysis, and comprehensive valuation metrics.

## 🎯 Module Scope & Boundaries

### ✅ What This Module Handles:
- Multi-scenario DCF calculations (worst/base/best case)
- Free Cash Flow projections
- Terminal value calculations
- WACC (Weighted Average Cost of Capital) computation
- Sensitivity analysis matrices
- Intrinsic value per share calculations
- Scenario comparison and analysis
- DCF model validation and quality scoring

### ❌ What This Module Does NOT Handle:
- Financial data fetching (handled by Data Module)
- User authentication (handled by User Module)
- Portfolio management (handled by Portfolio Module)
- Chart generation and visualization (handled by Report Module)

## 🏗️ Technical Architecture

### Database Schema
```sql
-- DCF calculation results storage
CREATE TABLE dcf_calculations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    ticker VARCHAR(10) NOT NULL,
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_data JSONB NOT NULL,
    scenario_results JSONB NOT NULL,
    sensitivity_data JSONB,
    quality_score DECIMAL(3,2),
    calculation_version VARCHAR(10) DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DCF model assumptions and parameters
CREATE TABLE dcf_assumptions (
    id SERIAL PRIMARY KEY,
    calculation_id INTEGER REFERENCES dcf_calculations(id) ON DELETE CASCADE,
    scenario_type VARCHAR(20) NOT NULL,
    revenue_growth_rate DECIMAL(5,4),
    margin_adjustment DECIMAL(5,4),
    discount_rate DECIMAL(5,4),
    terminal_growth_rate DECIMAL(5,4),
    projection_years INTEGER DEFAULT 5,
    confidence_level DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sensitivity analysis results
CREATE TABLE sensitivity_analyses (
    id SERIAL PRIMARY KEY,
    calculation_id INTEGER REFERENCES dcf_calculations(id) ON DELETE CASCADE,
    wacc_range JSONB NOT NULL,
    growth_range JSONB NOT NULL,
    value_matrix JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Core Classes & Models

#### DCF Calculation Engine
```python
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, validator
from datetime import datetime
import numpy as np

class DCFInputData(BaseModel):
    ticker: str
    current_price: float
    shares_outstanding: float
    revenue_history: List[float]  # 5 years of revenue
    operating_cash_flow: List[float]  # 5 years of OCF
    capex: List[float]  # 5 years of CapEx
    working_capital_changes: List[float]  # 5 years of WC changes
    total_debt: float
    cash_and_equivalents: float
    market_cap: float
    beta: float
    risk_free_rate: float
    market_risk_premium: float
    tax_rate: float
    
    @validator('revenue_history', 'operating_cash_flow', 'capex')
    def validate_history_length(cls, v):
        if len(v) < 3:
            raise ValueError('Need at least 3 years of historical data')
        return v

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

class SensitivityAnalysis(BaseModel):
    wacc_range: List[float]
    growth_range: List[float]
    value_matrix: List[List[float]]
    current_wacc: float
    current_growth: float
    base_case_value: float

class DCFAnalysisResult(BaseModel):
    ticker: str
    calculation_id: int
    current_market_price: float
    scenarios: Dict[str, DCFScenarioResult]
    sensitivity_analysis: SensitivityAnalysis
    quality_score: float
    calculation_timestamp: datetime
    data_freshness_score: float

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
    
    async def calculate_comprehensive_dcf(self, input_data: DCFInputData) -> DCFAnalysisResult:
        """
        Perform complete DCF analysis across all scenarios
        """
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
        
        # 5. Store calculation in database
        calculation_id = await self.store_calculation_results(
            input_data, scenario_results, sensitivity_analysis, quality_score
        )
        
        return DCFAnalysisResult(
            ticker=input_data.ticker,
            calculation_id=calculation_id,
            current_market_price=input_data.current_price,
            scenarios=scenario_results,
            sensitivity_analysis=sensitivity_analysis,
            quality_score=quality_score,
            calculation_timestamp=datetime.utcnow(),
            data_freshness_score=self.calculate_data_freshness(input_data)
        )
    
    async def calculate_scenario_dcf(self, input_data: DCFInputData, 
                                   parameters: ScenarioParameters, 
                                   scenario_name: str) -> DCFScenarioResult:
        """
        Calculate DCF for a specific scenario
        """
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
    
    def project_revenues(self, input_data: DCFInputData, 
                        parameters: ScenarioParameters) -> List[float]:
        """
        Project future revenues based on historical data and scenario parameters
        """
        # Calculate historical growth rate
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
    
    def calculate_projected_fcf(self, input_data: DCFInputData, 
                               projected_revenues: List[float],
                               parameters: ScenarioParameters) -> List[float]:
        """
        Calculate projected free cash flows
        """
        # Calculate historical FCF margins
        historical_fcf = []
        for i in range(len(input_data.revenue_history)):
            fcf = (input_data.operating_cash_flow[i] - input_data.capex[i] - 
                   input_data.working_capital_changes[i])
            historical_fcf.append(fcf)
        
        # Calculate average FCF margin
        fcf_margins = [fcf / rev for fcf, rev in 
                      zip(historical_fcf, input_data.revenue_history)]
        avg_fcf_margin = np.mean(fcf_margins[-3:])  # Use last 3 years
        
        # Apply scenario margin adjustment
        adjusted_margin = avg_fcf_margin * parameters.margin_adjustment
        
        # Project FCF
        projected_fcf = []
        for revenue in projected_revenues:
            fcf = revenue * adjusted_margin
            projected_fcf.append(fcf)
        
        return projected_fcf
    
    def calculate_terminal_value(self, final_fcf: float, 
                                terminal_growth_rate: float, 
                                discount_rate: float) -> float:
        """
        Calculate terminal value using Gordon Growth Model
        """
        if discount_rate <= terminal_growth_rate:
            raise ValueError("Discount rate must be greater than terminal growth rate")
        
        terminal_fcf = final_fcf * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
        
        return terminal_value
    
    def discount_to_present_value(self, cash_flows: List[float], 
                                 terminal_value: float, 
                                 discount_rate: float) -> List[float]:
        """
        Discount future cash flows to present value
        """
        present_values = []
        
        # Discount projected cash flows
        for i, cf in enumerate(cash_flows):
            pv = cf / ((1 + discount_rate) ** (i + 1))
            present_values.append(pv)
        
        # Discount terminal value
        terminal_pv = terminal_value / ((1 + discount_rate) ** len(cash_flows))
        present_values.append(terminal_pv)
        
        return present_values
    
    def calculate_wacc(self, input_data: DCFInputData) -> float:
        """
        Calculate Weighted Average Cost of Capital
        """
        # Cost of equity using CAPM
        cost_of_equity = (input_data.risk_free_rate + 
                         input_data.beta * input_data.market_risk_premium)
        
        # Assume cost of debt (simplified)
        cost_of_debt = input_data.risk_free_rate + 0.02  # Risk-free rate + 2% spread
        
        # Market values
        market_value_equity = input_data.market_cap
        market_value_debt = input_data.total_debt
        total_value = market_value_equity + market_value_debt
        
        # WACC calculation
        if total_value == 0:
            return cost_of_equity
        
        equity_weight = market_value_equity / total_value
        debt_weight = market_value_debt / total_value
        
        wacc = (equity_weight * cost_of_equity + 
                debt_weight * cost_of_debt * (1 - input_data.tax_rate))
        
        return wacc
    
    def generate_sensitivity_analysis(self, input_data: DCFInputData, 
                                    base_case: DCFScenarioResult) -> SensitivityAnalysis:
        """
        Generate sensitivity analysis matrix
        """
        # Define ranges for sensitivity analysis
        base_wacc = base_case.discount_rate
        base_growth = base_case.terminal_growth_rate
        
        wacc_range = [base_wacc + i * 0.005 for i in range(-4, 5)]  # ±2%
        growth_range = [base_growth + i * 0.0025 for i in range(-4, 5)]  # ±1%
        
        # Calculate value matrix
        value_matrix = []
        for wacc in wacc_range:
            row = []
            for growth in growth_range:
                # Recalculate intrinsic value with new parameters
                adjusted_params = base_case.assumptions.copy()
                adjusted_params.discount_rate = wacc
                adjusted_params.terminal_growth_rate = growth
                
                # Quick recalculation for sensitivity
                terminal_value = self.calculate_terminal_value(
                    base_case.projected_cash_flows[-1], growth, wacc
                )
                present_values = self.discount_to_present_value(
                    base_case.projected_cash_flows, terminal_value, wacc
                )
                
                total_pv = sum(present_values)
                equity_value = (total_pv - input_data.total_debt + 
                               input_data.cash_and_equivalents)
                intrinsic_value = equity_value / input_data.shares_outstanding
                
                row.append(round(intrinsic_value, 2))
            value_matrix.append(row)
        
        return SensitivityAnalysis(
            wacc_range=wacc_range,
            growth_range=growth_range,
            value_matrix=value_matrix,
            current_wacc=base_wacc,
            current_growth=base_growth,
            base_case_value=base_case.intrinsic_value_per_share
        )
    
    def calculate_data_quality_score(self, input_data: DCFInputData) -> float:
        """
        Calculate data quality score (0-1)
        """
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

## 🔌 API Endpoints

### DCF Analysis Endpoints
```python
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

router = APIRouter(prefix="/api/v1/dcf", tags=["dcf-analysis"])

@router.post("/analyze/{ticker}")
async def calculate_dcf_analysis(
    ticker: str,
    background_tasks: BackgroundTasks,
    current_user_id: int = Depends(get_user_id),
    dcf_engine: DCFCalculationEngine = Depends(get_dcf_engine)
):
    """
    Perform comprehensive DCF analysis for a stock ticker
    """
    try:
        # This would typically get data from Data Module
        input_data = await get_financial_data_for_dcf(ticker)
        
        # Perform DCF calculation
        analysis_result = await dcf_engine.calculate_comprehensive_dcf(input_data)
        
        # Store user association
        await associate_calculation_with_user(
            analysis_result.calculation_id, current_user_id
        )
        
        return analysis_result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DCF calculation error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal calculation error"
        )

@router.get("/analysis/{calculation_id}")
async def get_dcf_analysis(
    calculation_id: int,
    current_user_id: int = Depends(get_user_id),
    dcf_service: DCFService = Depends(get_dcf_service)
):
    """
    Retrieve stored DCF analysis by ID
    """
    analysis = await dcf_service.get_calculation_by_id(calculation_id)
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DCF analysis not found"
        )
    
    # Verify user access
    if analysis.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this analysis"
        )
    
    return analysis

@router.get("/history")
async def get_user_dcf_history(
    current_user_id: int = Depends(get_user_id),
    limit: int = 20,
    offset: int = 0,
    dcf_service: DCFService = Depends(get_dcf_service)
):
    """
    Get user's DCF calculation history
    """
    return await dcf_service.get_user_calculations(
        current_user_id, limit=limit, offset=offset
    )

@router.post("/custom-scenario")
async def calculate_custom_scenario(
    ticker: str,
    custom_parameters: ScenarioParameters,
    current_user_id: int = Depends(get_user_id),
    dcf_engine: DCFCalculationEngine = Depends(get_dcf_engine)
):
    """
    Calculate DCF with custom scenario parameters
    """
    input_data = await get_financial_data_for_dcf(ticker)
    
    scenario_result = await dcf_engine.calculate_scenario_dcf(
        input_data, custom_parameters, "custom"
    )
    
    return scenario_result
```

## 🔗 Module Interfaces

### Outgoing Dependencies
```python
# Data Module - for financial data
async def get_financial_data_for_dcf(ticker: str) -> DCFInputData:
    """Get required financial data from Data Module"""
    # This function would call the Data Module's service
    pass

# User Module - for authentication
from user_module import get_user_id

# Portfolio Module - for saving analyses
async def save_dcf_to_portfolio(user_id: int, portfolio_id: int, 
                               calculation_id: int) -> bool:
    """Save DCF analysis to user's portfolio"""
    pass
```

### Incoming Dependencies
```python
# Services provided to other modules
class DCFInterface:
    async def get_dcf_summary(self, calculation_id: int) -> dict:
        """Provide DCF summary for other modules"""
        pass
    
    async def get_intrinsic_value(self, ticker: str) -> float:
        """Get latest intrinsic value for a ticker"""
        pass
    
    async def validate_dcf_quality(self, calculation_id: int) -> float:
        """Return quality score for DCF calculation"""
        pass
```

## 🧪 Testing Strategy

### Unit Tests
```python
import pytest
import numpy as np

class TestDCFCalculationEngine:
    def test_project_revenues(self):
        engine = DCFCalculationEngine()
        
        input_data = DCFInputData(
            ticker="TEST",
            revenue_history=[1000, 1100, 1200, 1300, 1400],
            # ... other required fields
        )
        
        parameters = ScenarioParameters(
            revenue_growth_rate=0.05,
            margin_adjustment=1.0,
            discount_rate=0.10,
            terminal_growth_rate=0.025,
            confidence_level=0.9
        )
        
        projected = engine.project_revenues(input_data, parameters)
        
        assert len(projected) == 5
        assert all(rev > 0 for rev in projected)
        assert projected[0] > input_data.revenue_history[-1]
    
    def test_calculate_wacc(self):
        engine = DCFCalculationEngine()
        
        input_data = DCFInputData(
            ticker="TEST",
            market_cap=10000000,
            total_debt=2000000,
            beta=1.2,
            risk_free_rate=0.03,
            market_risk_premium=0.06,
            tax_rate=0.25,
            # ... other required fields
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
    
    def test_discount_rate_validation(self):
        engine = DCFCalculationEngine()
        
        with pytest.raises(ValueError):
            engine.calculate_terminal_value(
                final_fcf=1000,
                terminal_growth_rate=0.10,
                discount_rate=0.08  # Lower than growth rate
            )
```

### Integration Tests
```python
class TestDCFEndpoints:
    @pytest.mark.asyncio
    async def test_dcf_analysis_endpoint(self, authenticated_client):
        response = await authenticated_client.post("/api/v1/dcf/analyze/AAPL")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "ticker" in data
        assert "scenarios" in data
        assert "sensitivity_analysis" in data
        assert len(data["scenarios"]) == 3  # worst, base, best
    
    @pytest.mark.asyncio
    async def test_custom_scenario(self, authenticated_client):
        custom_params = {
            "revenue_growth_rate": 0.06,
            "margin_adjustment": 1.02,
            "discount_rate": 0.09,
            "terminal_growth_rate": 0.03,
            "confidence_level": 0.85
        }
        
        response = await authenticated_client.post(
            "/api/v1/dcf/custom-scenario?ticker=AAPL",
            json=custom_params
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["scenario_name"] == "custom"
        assert "intrinsic_value_per_share" in data
```

## 📊 Performance Requirements

### Calculation Performance
- Single scenario DCF: < 500ms
- Multi-scenario analysis: < 2 seconds
- Sensitivity analysis: < 1 second
- Custom scenario: < 300ms

### Accuracy Requirements
- Terminal value calculations: ±0.01% precision
- Present value discounting: ±0.01% precision
- WACC calculations: ±0.001% precision

## 🚀 Deployment Considerations

### Calculation Caching
- Cache DCF results for 1 hour
- Cache sensitivity matrices for 30 minutes
- Invalidate cache when underlying data changes

### Error Handling
- Graceful handling of missing financial data
- Validation of calculation inputs
- Fallback scenarios for edge cases

---

This module provides the core valuation engine that powers the entire Investment App's analytical capabilities.