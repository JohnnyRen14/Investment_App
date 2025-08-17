# Report Module - Technical Specification

## 📋 Module Overview
**Purpose**: Generate interactive charts, visualizations, and shareable reports for DCF analysis results and portfolio data.

**Core Responsibility**: Transform financial data and DCF calculations into professional visualizations, charts, and exportable reports.

## 🎯 Module Scope & Boundaries

### ✅ What This Module Handles:
- Interactive DCF flow charts and visualizations
- Sensitivity analysis heatmaps
- Portfolio performance charts
- Comparison charts (intrinsic vs market value)
- PDF report generation
- Shareable report links
- Chart customization and styling
- Export functionality (PNG, PDF, Excel)
- Real-time chart updates

### ❌ What This Module Does NOT Handle:
- DCF calculations (handled by DCF Module)
- Data fetching (handled by Data Module)
- User authentication (handled by User Module)
- Portfolio management (handled by Portfolio Module)

## 🏗️ Technical Architecture

### Database Schema
```sql
-- Generated reports tracking
CREATE TABLE generated_reports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    report_type VARCHAR(50) NOT NULL,
    ticker VARCHAR(10),
    portfolio_id INTEGER REFERENCES portfolios(id),
    dcf_calculation_id INTEGER REFERENCES dcf_calculations(id),
    report_data JSONB NOT NULL,
    chart_configs JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- Shareable report links
CREATE TABLE shared_reports (
    id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES generated_reports(id) ON DELETE CASCADE,
    share_token VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(255),
    description TEXT,
    is_public BOOLEAN DEFAULT false,
    password_protected BOOLEAN DEFAULT false,
    password_hash VARCHAR(255),
    view_count INTEGER DEFAULT 0,
    max_views INTEGER,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chart templates and configurations
CREATE TABLE chart_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(100) UNIQUE NOT NULL,
    chart_type VARCHAR(50) NOT NULL,
    default_config JSONB NOT NULL,
    is_system_template BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Core Classes & Services

#### Chart Generation Service
```python
from typing import Dict, List, Optional, Union
from pydantic import BaseModel
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import base64
import io

class ChartConfig(BaseModel):
    chart_type: str
    title: str
    width: int = 800
    height: int = 600
    theme: str = "plotly_white"
    colors: List[str] = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444"]
    show_legend: bool = True
    export_format: str = "png"

class DCFChartData(BaseModel):
    ticker: str
    scenarios: Dict[str, Dict]
    sensitivity_data: Dict
    current_price: float
    calculation_date: datetime

class ChartGenerationService:
    def __init__(self):
        self.default_config = ChartConfig(
            chart_type="dcf_flow",
            title="DCF Analysis",
            theme="plotly_white"
        )
    
    def generate_dcf_flow_chart(self, dcf_data: DCFChartData, config: ChartConfig) -> Dict:
        """
        Generate DCF cash flow visualization chart
        """
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Cash Flow Projections', 'Scenario Comparison', 
                          'Sensitivity Analysis', 'Intrinsic vs Market Value'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"type": "heatmap"}, {"type": "indicator"}]]
        )
        
        # 1. Cash Flow Projections (Top Left)
        years = list(range(1, 6))
        base_case = dcf_data.scenarios.get('base_case', {})
        projected_fcf = base_case.get('projected_cash_flows', [])
        
        fig.add_trace(
            go.Bar(
                x=years,
                y=projected_fcf,
                name='Projected FCF',
                marker_color=config.colors[0]
            ),
            row=1, col=1
        )
        
        # 2. Scenario Comparison (Top Right)
        scenario_names = []
        intrinsic_values = []
        
        for scenario_name, scenario_data in dcf_data.scenarios.items():
            scenario_names.append(scenario_name.replace('_', ' ').title())
            intrinsic_values.append(scenario_data.get('intrinsic_value_per_share', 0))
        
        fig.add_trace(
            go.Bar(
                x=scenario_names,
                y=intrinsic_values,
                name='Intrinsic Value',
                marker_color=config.colors[1]
            ),
            row=1, col=2
        )
        
        # Add current market price line
        fig.add_hline(
            y=dcf_data.current_price,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Market Price: ${dcf_data.current_price:.2f}",
            row=1, col=2
        )
        
        # 3. Sensitivity Analysis Heatmap (Bottom Left)
        sensitivity = dcf_data.sensitivity_data
        fig.add_trace(
            go.Heatmap(
                z=sensitivity.get('value_matrix', []),
                x=[f"{g*100:.1f}%" for g in sensitivity.get('growth_range', [])],
                y=[f"{w*100:.1f}%" for w in sensitivity.get('wacc_range', [])],
                colorscale='RdYlGn',
                name='Sensitivity'
            ),
            row=2, col=1
        )
        
        # 4. Intrinsic vs Market Value Gauge (Bottom Right)
        base_intrinsic = base_case.get('intrinsic_value_per_share', 0)
        upside_percentage = ((base_intrinsic - dcf_data.current_price) / dcf_data.current_price) * 100
        
        fig.add_trace(
            go.Indicator(
                mode="gauge+number+delta",
                value=upside_percentage,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Upside/Downside %"},
                delta={'reference': 0},
                gauge={
                    'axis': {'range': [-50, 50]},
                    'bar': {'color': config.colors[2]},
                    'steps': [
                        {'range': [-50, -10], 'color': "lightgray"},
                        {'range': [-10, 10], 'color': "gray"},
                        {'range': [10, 50], 'color': "lightgreen"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 0
                    }
                }
            ),
            row=2, col=2
        )
        
        # Update layout
        fig.update_layout(
            title=f"{config.title} - {dcf_data.ticker}",
            template=config.theme,
            height=config.height,
            width=config.width,
            showlegend=config.show_legend
        )
        
        return {
            "chart_html": fig.to_html(),
            "chart_json": fig.to_json(),
            "chart_image": self.fig_to_base64(fig, config.export_format)
        }
    
    def generate_portfolio_performance_chart(self, portfolio_data: Dict, config: ChartConfig) -> Dict:
        """
        Generate portfolio performance visualization
        """
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Portfolio Value Over Time', 'Asset Allocation', 
                          'Top Holdings Performance', 'Sector Distribution'),
            specs=[[{"secondary_y": True}, {"type": "pie"}],
                   [{"secondary_y": False}, {"type": "pie"}]]
        )
        
        # Portfolio performance charts implementation
        # ... (implementation details)
        
        return {
            "chart_html": fig.to_html(),
            "chart_json": fig.to_json(),
            "chart_image": self.fig_to_base64(fig, config.export_format)
        }
    
    def fig_to_base64(self, fig, format_type: str = "png") -> str:
        """Convert plotly figure to base64 encoded image"""
        img_bytes = fig.to_image(format=format_type)
        img_base64 = base64.b64encode(img_bytes).decode()
        return f"data:image/{format_type};base64,{img_base64}"
```

#### PDF Report Service
```python
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile
import os

class PDFReportService:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.custom_styles = self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Create custom styles for PDF reports"""
        return {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor('#1f2937')
            ),
            'subtitle': ParagraphStyle(
                'CustomSubtitle',
                parent=self.styles['Heading2'],
                fontSize=16,
                spaceAfter=20,
                textColor=colors.HexColor('#374151')
            ),
            'body': ParagraphStyle(
                'CustomBody',
                parent=self.styles['Normal'],
                fontSize=11,
                spaceAfter=12,
                textColor=colors.HexColor('#4b5563')
            )
        }
    
    def generate_dcf_report(self, dcf_data: Dict, chart_images: Dict) -> bytes:
        """Generate comprehensive DCF analysis PDF report"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Title
        title = Paragraph(
            f"DCF Analysis Report - {dcf_data['ticker']}", 
            self.custom_styles['title']
        )
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Executive Summary
        summary_title = Paragraph("Executive Summary", self.custom_styles['subtitle'])
        story.append(summary_title)
        
        base_case = dcf_data['scenarios']['base_case']
        intrinsic_value = base_case['intrinsic_value_per_share']
        current_price = dcf_data['current_market_price']
        upside = ((intrinsic_value - current_price) / current_price) * 100
        
        summary_text = f"""
        <b>Ticker:</b> {dcf_data['ticker']}<br/>
        <b>Current Market Price:</b> ${current_price:.2f}<br/>
        <b>Intrinsic Value (Base Case):</b> ${intrinsic_value:.2f}<br/>
        <b>Upside/Downside:</b> {upside:+.1f}%<br/>
        <b>Analysis Date:</b> {dcf_data['calculation_timestamp'].strftime('%Y-%m-%d')}<br/>
        <b>Data Quality Score:</b> {dcf_data['quality_score']:.1%}
        """
        
        summary_para = Paragraph(summary_text, self.custom_styles['body'])
        story.append(summary_para)
        story.append(Spacer(1, 20))
        
        # Scenario Analysis Table
        scenario_title = Paragraph("Scenario Analysis", self.custom_styles['subtitle'])
        story.append(scenario_title)
        
        scenario_data = [
            ['Scenario', 'Intrinsic Value', 'Upside/Downside', 'Confidence Level']
        ]
        
        for scenario_name, scenario in dcf_data['scenarios'].items():
            upside_pct = ((scenario['intrinsic_value_per_share'] - current_price) / current_price) * 100
            scenario_data.append([
                scenario_name.replace('_', ' ').title(),
                f"${scenario['intrinsic_value_per_share']:.2f}",
                f"{upside_pct:+.1f}%",
                f"{scenario['assumptions']['confidence_level']:.0%}"
            ])
        
        scenario_table = Table(scenario_data)
        scenario_table.setStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        
        story.append(scenario_table)
        story.append(Spacer(1, 20))
        
        # Add charts if available
        if chart_images.get('dcf_flow_chart'):
            chart_title = Paragraph("DCF Analysis Charts", self.custom_styles['subtitle'])
            story.append(chart_title)
            
            # Convert base64 to image
            chart_img = self._base64_to_image(chart_images['dcf_flow_chart'])
            if chart_img:
                story.append(chart_img)
                story.append(Spacer(1, 20))
        
        # Key Assumptions
        assumptions_title = Paragraph("Key Assumptions", self.custom_styles['subtitle'])
        story.append(assumptions_title)
        
        base_assumptions = base_case['assumptions']
        assumptions_text = f"""
        <b>Revenue Growth Rate:</b> {base_assumptions['revenue_growth_rate']:.1%}<br/>
        <b>Discount Rate (WACC):</b> {base_assumptions['discount_rate']:.1%}<br/>
        <b>Terminal Growth Rate:</b> {base_assumptions['terminal_growth_rate']:.1%}<br/>
        <b>Projection Period:</b> {base_assumptions['projection_years']} years<br/>
        """
        
        assumptions_para = Paragraph(assumptions_text, self.custom_styles['body'])
        story.append(assumptions_para)
        
        # Disclaimer
        story.append(Spacer(1, 30))
        disclaimer_title = Paragraph("Disclaimer", self.custom_styles['subtitle'])
        story.append(disclaimer_title)
        
        disclaimer_text = """
        This DCF analysis is for informational purposes only and should not be considered as investment advice. 
        The analysis is based on historical data and assumptions that may not reflect future performance. 
        Please consult with a qualified financial advisor before making investment decisions.
        """
        
        disclaimer_para = Paragraph(disclaimer_text, self.custom_styles['body'])
        story.append(disclaimer_para)
        
        # Build PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def _base64_to_image(self, base64_string: str, max_width: float = 6*inch):
        """Convert base64 image to ReportLab Image"""
        try:
            # Remove data URL prefix if present
            if base64_string.startswith('data:image'):
                base64_string = base64_string.split(',')[1]
            
            img_data = base64.b64decode(base64_string)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                tmp_file.write(img_data)
                tmp_file_path = tmp_file.name
            
            # Create ReportLab Image
            img = Image(tmp_file_path, width=max_width, height=max_width*0.75)
            
            # Clean up temporary file
            os.unlink(tmp_file_path)
            
            return img
        except Exception as e:
            print(f"Error converting base64 to image: {e}")
            return None
```

#### Report Sharing Service
```python
import secrets
import hashlib
from datetime import datetime, timedelta

class ReportSharingService:
    def __init__(self, db_session):
        self.db = db_session
    
    async def create_shareable_report(self, user_id: int, report_data: Dict, 
                                    share_config: Dict) -> Dict:
        """Create a shareable report link"""
        
        # Generate unique share token
        share_token = secrets.token_urlsafe(32)
        
        # Create report record
        report = GeneratedReport(
            user_id=user_id,
            report_type=share_config.get('report_type', 'dcf_analysis'),
            ticker=report_data.get('ticker'),
            report_data=report_data,
            chart_configs=share_config.get('chart_configs', {}),
            expires_at=datetime.utcnow() + timedelta(days=share_config.get('expires_days', 30))
        )
        
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        
        # Create shared report link
        password_hash = None
        if share_config.get('password'):
            password_hash = hashlib.sha256(share_config['password'].encode()).hexdigest()
        
        shared_report = SharedReport(
            report_id=report.id,
            share_token=share_token,
            title=share_config.get('title', f"DCF Analysis - {report_data.get('ticker')}"),
            description=share_config.get('description'),
            is_public=share_config.get('is_public', False),
            password_protected=bool(share_config.get('password')),
            password_hash=password_hash,
            max_views=share_config.get('max_views'),
            expires_at=report.expires_at
        )
        
        self.db.add(shared_report)
        await self.db.commit()
        await self.db.refresh(shared_report)
        
        return {
            "share_token": share_token,
            "share_url": f"/shared-reports/{share_token}",
            "expires_at": shared_report.expires_at,
            "is_password_protected": shared_report.password_protected,
            "max_views": shared_report.max_views
        }
    
    async def get_shared_report(self, share_token: str, password: str = None) -> Optional[Dict]:
        """Retrieve shared report by token"""
        
        shared_report = await self.db.execute(
            select(SharedReport).where(SharedReport.share_token == share_token)
        )
        shared_report = shared_report.scalar_one_or_none()
        
        if not shared_report:
            return None
        
        # Check expiration
        if shared_report.expires_at and shared_report.expires_at < datetime.utcnow():
            return None
        
        # Check max views
        if shared_report.max_views and shared_report.view_count >= shared_report.max_views:
            return None
        
        # Check password
        if shared_report.password_protected:
            if not password:
                return {"requires_password": True}
            
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash != shared_report.password_hash:
                return {"error": "Invalid password"}
        
        # Get report data
        report = await self.db.get(GeneratedReport, shared_report.report_id)
        if not report:
            return None
        
        # Increment view count
        shared_report.view_count += 1
        await self.db.commit()
        
        return {
            "title": shared_report.title,
            "description": shared_report.description,
            "report_data": report.report_data,
            "chart_configs": report.chart_configs,
            "created_at": report.created_at,
            "view_count": shared_report.view_count
        }
```

## 🔌 API Endpoints

### Chart Generation Endpoints
```python
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

@router.post("/charts/dcf")
async def generate_dcf_chart(
    dcf_data: DCFChartData,
    chart_config: Optional[ChartConfig] = None,
    current_user_id: int = Depends(get_user_id),
    chart_service: ChartGenerationService = Depends(get_chart_service)
):
    """Generate DCF analysis chart"""
    try:
        config = chart_config or chart_service.default_config
        chart_result = chart_service.generate_dcf_flow_chart(dcf_data, config)
        
        return {
            "chart_html": chart_result["chart_html"],
            "chart_json": chart_result["chart_json"],
            "chart_image": chart_result["chart_image"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating chart: {str(e)}"
        )

@router.post("/charts/portfolio")
async def generate_portfolio_chart(
    portfolio_data: Dict,
    chart_config: Optional[ChartConfig] = None,
    current_user_id: int = Depends(get_user_id),
    chart_service: ChartGenerationService = Depends(get_chart_service)
):
    """Generate portfolio performance chart"""
    config = chart_config or chart_service.default_config
    chart_result = chart_service.generate_portfolio_performance_chart(portfolio_data, config)
    
    return chart_result

@router.post("/pdf/dcf")
async def generate_dcf_pdf_report(
    dcf_data: Dict,
    chart_images: Optional[Dict] = None,
    current_user_id: int = Depends(get_user_id),
    pdf_service: PDFReportService = Depends(get_pdf_service)
):
    """Generate PDF report for DCF analysis"""
    try:
        pdf_bytes = pdf_service.generate_dcf_report(dcf_data, chart_images or {})
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=dcf_analysis_{dcf_data['ticker']}.pdf"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating PDF: {str(e)}"
        )

@router.post("/share")
async def create_shared_report(
    report_data: Dict,
    share_config: Dict,
    current_user_id: int = Depends(get_user_id),
    sharing_service: ReportSharingService = Depends(get_sharing_service)
):
    """Create shareable report link"""
    try:
        share_result = await sharing_service.create_shareable_report(
            current_user_id, report_data, share_config
        )
        return share_result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating shared report: {str(e)}"
        )

@router.get("/shared/{share_token}")
async def get_shared_report(
    share_token: str,
    password: Optional[str] = None,
    sharing_service: ReportSharingService = Depends(get_sharing_service)
):
    """Access shared report by token"""
    try:
        report = await sharing_service.get_shared_report(share_token, password)
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shared report not found or expired"
            )
        
        if report.get("requires_password"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password required to access this report"
            )
        
        if report.get("error"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=report["error"]
            )
        
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error accessing shared report: {str(e)}"
        )
```

## 🔗 Module Interfaces

### Outgoing Dependencies
```python
# User Module - for authentication
from user_module import get_user_id

# DCF Module - for analysis data
async def get_dcf_analysis_data(calculation_id: int) -> Dict:
    """Get DCF analysis data for chart generation"""
    pass

# Portfolio Module - for portfolio data
async def get_portfolio_data(portfolio_id: int) -> Dict:
    """Get portfolio data for performance charts"""
    pass

# Data Module - for company information
async def get_company_info(ticker: str) -> Dict:
    """Get company information for reports"""
    pass
```

### Incoming Dependencies
```python
# Services provided to other modules
class ReportInterface:
    async def generate_quick_chart(self, data: Dict, chart_type: str) -> str:
        """Generate quick chart for other modules"""
        pass
    
    async def export_data_to_excel(self, data: Dict, filename: str) -> bytes:
        """Export data to Excel format"""
        pass
    
    async def create_thumbnail(self, chart_data: Dict) -> str:
        """Create thumbnail image for previews"""
        pass
```

## 🧪 Testing Strategy

### Unit Tests
```python
import pytest
from unittest.mock import Mock, patch
import plotly.graph_objects as go

class TestChartGenerationService:
    def test_dcf_chart_generation(self):
        service = ChartGenerationService()
        
        dcf_data = DCFChartData(
            ticker="AAPL",
            scenarios={
                "base_case": {
                    "projected_cash_flows": [1000, 1100, 1200, 1300, 1400],
                    "intrinsic_value_per_share": 150.0
                }
            },
            sensitivity_data={
                "value_matrix": [[140, 145, 150], [145, 150, 155]],
                "wacc_range": [0.08, 0.10],
                "growth_range": [0.02, 0.025, 0.03]
            },
            current_price=145.0,
            calculation_date=datetime.now()
        )
        
        config = ChartConfig(chart_type="dcf_flow", title="Test DCF")
        result = service.generate_dcf_flow_chart(dcf_data, config)
        
        assert "chart_html" in result
        assert "chart_json" in result
        assert "chart_image" in result
    
    def test_base64_conversion(self):
        service = ChartGenerationService()
        
        # Create simple figure
        fig = go.Figure(data=go.Bar(x=[1, 2, 3], y=[4, 5, 6]))
        
        base64_result = service.fig_to_base64(fig, "png")
        
        assert base64_result.startswith("data:image/png;base64,")
        assert len(base64_result) > 100  # Should have substantial content

class TestPDFReportService:
    def test_pdf_generation(self):
        service = PDFReportService()
        
        dcf_data = {
            "ticker": "AAPL",
            "current_market_price": 145.0,
            "scenarios": {
                "base_case": {
                    "intrinsic_value_per_share": 150.0,
                    "assumptions": {
                        "revenue_growth_rate": 0.05,
                        "discount_rate": 0.10,
                        "terminal_growth_rate": 0.025,
                        "projection_years": 5,
                        "confidence_level": 0.9
                    }
                }
            },
            "quality_score": 0.85,
            "calculation_timestamp": datetime.now()
        }
        
        pdf_bytes = service.generate_dcf_report(dcf_data, {})
        
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000  # Should be substantial PDF content
        assert pdf_bytes.startswith(b'%PDF')  # PDF header

class TestReportSharingService:
    @pytest.mark.asyncio
    async def test_create_shareable_report(self):
        mock_db = Mock()
        service = ReportSharingService(mock_db)
        
        report_data = {"ticker": "AAPL", "analysis": "test"}
        share_config = {
            "title": "Test Report",
            "expires_days": 7,
            "is_public": True
        }
        
        with patch.object(service, 'db') as mock_db_session:
            result = await service.create_shareable_report(1, report_data, share_config)
            
            assert "share_token" in result
            assert "share_url" in result
            assert "expires_at" in result
            assert len(result["share_token"]) > 20  # Should be substantial token
```

### Integration Tests
```python
class TestReportEndpoints:
    @pytest.mark.asyncio
    async def test_generate_dcf_chart_endpoint(self, authenticated_client):
        dcf_data = {
            "ticker": "AAPL",
            "scenarios": {
                "base_case": {
                    "projected_cash_flows": [1000, 1100, 1200, 1300, 1400],
                    "intrinsic_value_per_share": 150.0
                }
            },
            "sensitivity_data": {
                "value_matrix": [[140, 145, 150]],
                "wacc_range": [0.10],
                "growth_range": [0.02, 0.025, 0.03]
            },
            "current_price": 145.0,
            "calculation_date": "2024-01-01T00:00:00"
        }
        
        response = await authenticated_client.post("/api/v1/reports/charts/dcf", json=dcf_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "chart_html" in data
        assert "chart_json" in data
        assert "chart_image" in data
    
    @pytest.mark.asyncio
    async def test_pdf_generation_endpoint(self, authenticated_client):
        dcf_data = {
            "ticker": "AAPL",
            "current_market_price": 145.0,
            "scenarios": {"base_case": {"intrinsic_value_per_share": 150.0}},
            "quality_score": 0.85,
            "calculation_timestamp": "2024-01-01T00:00:00"
        }
        
        response = await authenticated_client.post("/api/v1/reports/pdf/dcf", json=dcf_data)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert len(response.content) > 1000
    
    @pytest.mark.asyncio
    async def test_share_report_workflow(self, authenticated_client):
        # Create shared report
        report_data = {"ticker": "AAPL", "analysis": "test"}
        share_config = {"title": "Test Report", "is_public": True}
        
        create_response = await authenticated_client.post(
            "/api/v1/reports/share",
            json={"report_data": report_data, "share_config": share_config}
        )
        
        assert create_response.status_code == 200
        share_data = create_response.json()
        share_token = share_data["share_token"]
        
        # Access shared report
        access_response = await authenticated_client.get(f"/api/v1/reports/shared/{share_token}")
        
        assert access_response.status_code == 200
        accessed_data = access_response.json()
        assert accessed_data["title"] == "Test Report"
        assert accessed_data["report_data"]["ticker"] == "AAPL"
```

## 📊 Performance Requirements

### Chart Generation
- Simple charts: < 500ms
- Complex multi-panel charts: < 2 seconds
- PDF generation: < 3 seconds
- Image export: < 1 second

### Caching Strategy
- Chart templates: Cache for 1 hour
- Generated charts: Cache for 15 minutes
- PDF reports: Cache for 30 minutes
- Shared report data: Cache for 5 minutes

## 🚀 Deployment Considerations

### Dependencies
```bash
# Python packages
plotly>=5.0.0
reportlab>=3.6.0
pandas>=1.5.0
pillow>=9.0.0
kaleido>=0.2.1  # For static image export

# System dependencies
wkhtmltopdf  # Alternative PDF generation
```

### Environment Variables
```bash
CHART_CACHE_TTL=900
PDF_CACHE_TTL=1800
SHARED_REPORT_BASE_URL=https://yourapp.com
MAX_CHART_WIDTH=1200
MAX_CHART_HEIGHT=800
ENABLE_CHART_ANIMATIONS=false
```

### Performance Optimization
- Use CDN for chart assets
- Implement chart caching
- Optimize image compression
- Lazy load chart components
- Use WebGL for large datasets

---

This module provides comprehensive reporting and visualization capabilities that transform raw financial data into professional, shareable insights for investment decision-making.