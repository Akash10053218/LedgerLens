"""
LedgerLens Data Models
Pydantic schemas for Invoices, Expense Line Items, Audit Flags, and Tax Summaries.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class LineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    amount: float = 0.0


class AuditFlag(BaseModel):
    severity: str = "warning"  # "info", "warning", "critical"
    code: str                  # e.g., "MATH_MISMATCH", "HIGH_EXPENSE", "MEAL_50_RULE"
    title: str
    message: str
    recommendation: Optional[str] = None


class InvoiceData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = "document.pdf"
    vendor: str = "Unknown Vendor"
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    due_date: Optional[str] = None
    currency: str = "USD"
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    payment_method: Optional[str] = None
    category: str = "Uncategorized"
    schedule_c_line: str = "Line 27a: Other expenses"
    deductible_percentage: float = 100.0
    deductible_amount: float = 0.0
    business_purpose: str = "General business expense"
    line_items: List[LineItem] = []
    audit_flags: List[AuditFlag] = []
    confidence_score: float = 0.85
    extraction_method: str = "Hybrid Open AI"
    raw_text: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExpenseSummary(BaseModel):
    total_spend: float = 0.0
    total_deductible: float = 0.0
    total_tax_paid: float = 0.0
    estimated_tax_savings: float = 0.0
    effective_tax_rate: float = 30.0  # Default 30% self-employment + income tax
    total_documents: int = 0
    categories_breakdown: Dict[str, float] = {}
    audit_risk_score: str = "Low"     # "Low", "Moderate", "High"
    flagged_issues_count: int = 0


class AISettings(BaseModel):
    provider: str = "hybrid"          # "hybrid", "gemma2", "ollama", "huggingface"
    ollama_url: Optional[str] = "http://localhost:11434"
    model_name: Optional[str] = "gemma2:9b"
    hf_token: Optional[str] = None
    custom_endpoint: Optional[str] = None
