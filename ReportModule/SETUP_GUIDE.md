# Report Module - Development Setup Guide

## 📋 Module Overview
**Responsibility**: Generate interactive charts, visualizations, and shareable reports for DCF analysis results and portfolio data.

## 🎯 What's Already Set Up
- ✅ Project structure with backend/frontend folders
- ✅ FastAPI main application (`backend/main.py`)
- ✅ Next.js configuration
- ✅ Docker configuration
- ✅ Database structure defined
- ✅ Module specification (`REPORT_MODULE_CLAUDE.md`)

## 🚀 Your Development Tasks

### 1. Backend Implementation
**Location**: `backend/app/api/reports/`

**Files to Create**:
```
backend/app/api/reports/
├── __init__.py
├── routes.py          # Report generation endpoints
├── schemas.py         # Pydantic models for reports
├── services.py        # Report business logic
├── chart_service.py   # Chart generation service
├── pdf_service.py     # PDF generation service
└── sharing_service.py # Report sharing service
```

**Key Components to Implement**:
- `ChartGenerationService` class (from specification)
- `PDFReportService` class (from specification)
- `ReportSharingService` class (from specification)
- Interactive chart generation with Plotly
- PDF report generation with ReportLab
- Shareable report links with security

### 2. Database Models
**Location**: `backend/app/models/`

**Files to Create**:
```
backend/app/models/
├── reports.py         # Report models
└── charts.py          # Chart configuration models
```

**Models to Implement**:
- `GeneratedReport` model
- `SharedReport` model
- `ChartTemplate` model

## 🔧 Development Environment Setup

### Backend Setup
1. **Install Additional Dependencies**:
```bash
cd backend
pip install plotly kaleido reportlab weasyprint openpyxl xlsxwriter pillow
```

2. **Create Database Models**:
```python
# backend/app/models/reports.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    report_type = Column(String(50), nullable=False)
    ticker = Column(String(10))
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    dcf_calculation_id = Column(Integer, ForeignKey("dcf_calculations.id"))
    report_data = Column(JSONB, nullable=False)
    chart_configs = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    shared_reports = relationship("SharedReport", back_populates="report", cascade="all, delete-orphan")

class SharedReport(Base):
    __tablename__ = "shared_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False)
    share_token = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255))
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    password_protected = Column(Boolean, default=False)
    password_hash = Column(String(255))
    view_count = Column(Integer, default=0)
    max_views = Column(Integer)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    report = relationship("GeneratedReport", back_populates="shared_reports")
```

3. **Create Chart Generation Service**:
```python
# backend/app/api/reports/chart_service.py
from typing import Dict, List, Optional
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import base64
import io
from pydantic import BaseModel

class ChartConfig(BaseModel):
    chart_type: str
    title: str
    width: int = 800
    height: int = 600
    theme: str = "plotly_white"
    colors: List[str] = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444"]
    show_legend: bool = True
    export_format: str = "png"

class ChartGenerationService:
    def __init__(self):
        self.default_config = ChartConfig(
            chart_type="dcf_flow",
            title="DCF Analysis",
            theme="plotly_white"
        )
    
    def generate_dcf_flow_chart(self, dcf_data: Dict, config: ChartConfig) -> Dict:
        """Generate DCF cash flow visualization chart"""
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Cash Flow Projections', 'Scenario Comparison', 
                          'Sensitivity Analysis', 'Intrinsic vs Market Value'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"type": "heatmap"}, {"type": "indicator"}]]
        )
        
        # 1. Cash Flow Projections (Top Left)
        years = list(range(1, 6))
        base_case = dcf_data['scenarios'].get('base_case', {})
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
        
        for scenario_name, scenario_data in dcf_data['scenarios'].items():
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
        current_price = dcf_data.get('current_market_price', 0)
        fig.add_hline(
            y=current_price,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Market Price: ${current_price:.2f}",
            row=1, col=2
        )
        
        # 3. Sensitivity Analysis Heatmap (Bottom Left)
        sensitivity = dcf_data.get('sensitivity_analysis', {})
        if sensitivity:
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
        upside_percentage = ((base_intrinsic - current_price) / current_price) * 100 if current_price > 0 else 0
        
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
            title=f"{config.title} - {dcf_data.get('ticker', 'Unknown')}",
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
        """Generate portfolio performance visualization"""
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Portfolio Value Over Time', 'Asset Allocation', 
                          'Top Holdings Performance', 'Sector Distribution'),
            specs=[[{"secondary_y": True}, {"type": "pie"}],
                   [{"secondary_y": False}, {"type": "pie"}]]
        )
        
        # Implementation for portfolio charts...
        # (Similar structure to DCF charts)
        
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

4. **Create PDF Report Service**:
```python
# backend/app/api/reports/pdf_service.py
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile
import os
import io
from datetime import datetime

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
    
    def generate_dcf_report(self, dcf_data: Dict, chart_images: Dict = None) -> bytes:
        """Generate comprehensive DCF analysis PDF report"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Title
        title = Paragraph(
            f"DCF Analysis Report - {dcf_data.get('ticker', 'Unknown')}", 
            self.custom_styles['title']
        )
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Executive Summary
        summary_title = Paragraph("Executive Summary", self.custom_styles['subtitle'])
        story.append(summary_title)
        
        base_case = dcf_data.get('scenarios', {}).get('base_case', {})
        intrinsic_value = base_case.get('intrinsic_value_per_share', 0)
        current_price = dcf_data.get('current_market_price', 0)
        upside = ((intrinsic_value - current_price) / current_price) * 100 if current_price > 0 else 0
        
        summary_text = f"""
        <b>Ticker:</b> {dcf_data.get('ticker', 'Unknown')}<br/>
        <b>Current Market Price:</b> ${current_price:.2f}<br/>
        <b>Intrinsic Value (Base Case):</b> ${intrinsic_value:.2f}<br/>
        <b>Upside/Downside:</b> {upside:+.1f}%<br/>
        <b>Analysis Date:</b> {datetime.now().strftime('%Y-%m-%d')}<br/>
        <b>Data Quality Score:</b> {dcf_data.get('quality_score', 0):.1%}
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
        
        for scenario_name, scenario in dcf_data.get('scenarios', {}).items():
            upside_pct = ((scenario.get('intrinsic_value_per_share', 0) - current_price) / current_price) * 100 if current_price > 0 else 0
            scenario_data.append([
                scenario_name.replace('_', ' ').title(),
                f"${scenario.get('intrinsic_value_per_share', 0):.2f}",
                f"{upside_pct:+.1f}%",
                f"{scenario.get('assumptions', {}).get('confidence_level', 0):.0%}"
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
        
        # Add disclaimer
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
```

### Frontend Setup
1. **Install Additional Dependencies**:
```bash
cd frontend
npm install plotly.js react-plotly.js @types/plotly.js html2canvas jspdf file-saver @types/file-saver
```

2. **Create Chart Components**:
```typescript
// frontend/src/components/charts/DCFFlowChart.tsx
import React from 'react';
import Plot from 'react-plotly.js';

interface DCFChartProps {
  dcfData: any;
  config?: {
    width?: number;
    height?: number;
    theme?: string;
  };
}

const DCFFlowChart: React.FC<DCFChartProps> = ({ dcfData, config = {} }) => {
  const {
    width = 800,
    height = 600,
    theme = 'plotly_white'
  } = config;

  // Prepare data for charts
  const baseCase = dcfData.scenarios?.base_case || {};
  const projectedFCF = baseCase.projected_cash_flows || [];
  const years = Array.from({ length: projectedFCF.length }, (_, i) => `Year ${i + 1}`);

  // Scenario comparison data
  const scenarioNames = Object.keys(dcfData.scenarios || {}).map(name => 
    name.replace('_', ' ').toUpperCase()
  );
  const intrinsicValues = Object.values(dcfData.scenarios || {}).map((scenario: any) => 
    scenario.intrinsic_value_per_share || 0
  );

  const data = [
    {
      x: years,
      y: projectedFCF,
      type: 'bar' as const,
      name: 'Projected FCF',
      marker: { color: '#3B82F6' },
      xaxis: 'x',
      yaxis: 'y'
    },
    {
      x: scenarioNames,
      y: intrinsicValues,
      type: 'bar' as const,
      name: 'Intrinsic Value',
      marker: { color: '#10B981' },
      xaxis: 'x2',
      yaxis: 'y2'
    }
  ];

  const layout = {
    title: `DCF Analysis - ${dcfData.ticker || 'Unknown'}`,
    template: theme,
    width,
    height,
    grid: { rows: 2, columns: 2, pattern: 'independent' },
    xaxis: { domain: [0, 0.45], title: 'Projection Years' },
    yaxis: { domain: [0.55, 1], title: 'Cash Flow ($M)' },
    xaxis2: { domain: [0.55, 1], title: 'Scenarios' },
    yaxis2: { domain: [0.55, 1], title: 'Intrinsic Value ($)' },
    showlegend: true,
    shapes: [
      {
        type: 'line',
        x0: 0,
        x1: 1,
        y0: dcfData.current_market_price,
        y1: dcfData.current_market_price,
        xref: 'x2 domain',
        yref: 'y2',
        line: { color: 'red', dash: 'dash', width: 2 }
      }
    ],
    annotations: [
      {
        x: 0.5,
        y: dcfData.current_market_price,
        xref: 'x2 domain',
        yref: 'y2',
        text: `Market Price: $${dcfData.current_market_price?.toFixed(2) || '0.00'}`,
        showarrow: true,
        arrowhead: 2,
        arrowcolor: 'red'
      }
    ]
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-lg">
      <Plot
        data={data}
        layout={layout}
        config={{
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d']
        }}
      />
    </div>
  );
};

export default DCFFlowChart;
```

## 📚 Integration Points

### Dependencies on Other Modules
- **User Module**: Authentication for report access
- **DCF Module**: DCF analysis data for chart generation
- **Portfolio Module**: Portfolio data for performance charts
- **Data Module**: Company information for reports

### Services Provided to Other Modules
```python
# Services other modules can use
class ReportInterface:
    async def generate_quick_chart(self, data: Dict, chart_type: str) -> str:
        """Generate quick chart for other modules"""
        pass
    
    async def create_thumbnail(self, chart_data: Dict) -> str:
        """Create thumbnail image for previews"""
        pass
```

### API Endpoints to Implement
```
POST /api/v1/reports/charts/dcf              # Generate DCF chart
POST /api/v1/reports/charts/portfolio        # Generate portfolio chart
POST /api/v1/reports/pdf/dcf                 # Generate DCF PDF
POST /api/v1/reports/share                   # Create shared report
GET  /api/v1/reports/shared/{share_token}    # Access shared report
```

## 📋 Checklist
- [ ] Create database models for reports and sharing
- [ ] Implement chart generation service with Plotly
- [ ] Create PDF generation service with ReportLab
- [ ] Implement report sharing with secure tokens
- [ ] Create API endpoints for report generation
- [ ] Build frontend chart components
- [ ] Add export functionality (PNG, PDF)
- [ ] Write unit tests for chart generation
- [ ] Write integration tests for API endpoints
- [ ] Test PDF generation with sample data
- [ ] Update main.py to include reports router
- [ ] Test integration with other modules

## 🚨 Important Notes
- **Performance**: Chart generation can be CPU intensive
- **Security**: Validate shared report access properly
- **File Size**: Optimize PDF and image file sizes
- **Browser Compatibility**: Test charts across different browsers
- **Mobile**: Ensure charts are responsive
- **Caching**: Cache generated charts and PDFs appropriately

## 📞 Need Help?
- Check `REPORT_MODULE_CLAUDE.md` for detailed specifications
- Review Plotly.js documentation for chart customization
- Test chart generation with sample DCF data
- Use `/docs` endpoint to test your API endpoints
```