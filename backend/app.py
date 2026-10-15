"""
LedgerLens FastAPI Application
Production-ready REST API for privacy-first AI invoice & expense auditing.
"""

import io
import csv
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime, timezone

from .models import InvoiceData, ExpenseSummary, AISettings
from .extractor import DocumentExtractor
from .sample_data import SAMPLE_INVOICES
from .tax_rules import classify_expense, audit_check_invoice

app = FastAPI(
    title="LedgerLens",
    description="Privacy-First AI Invoice & Expense Auditor for Freelancers & Solopreneurs",
    version="1.0.0"
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (initialized with realistic sample data)
invoices_store: List[InvoiceData] = [inv.model_copy(deep=True) for inv in SAMPLE_INVOICES]
current_settings: AISettings = AISettings()
extractor: DocumentExtractor = DocumentExtractor(current_settings)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "LedgerLens",
        "version": "1.0.0",
        "open_source_core": True,
        "default_model": "Gemma-2-9b / Hybrid Open NLP",
        "provider": current_settings.provider,
        "documents_count": len(invoices_store),
        "render_optimized": True
    }


@app.get("/api/invoices", response_model=List[InvoiceData])
def get_invoices():
    return invoices_store


@app.post("/api/invoices/upload", response_model=InvoiceData)
async def upload_invoice(file: UploadFile = File(...)):
    """
    Upload and parse an invoice or receipt image/PDF using open-source extraction.
    """
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Run extraction
    filename = file.filename or "uploaded_invoice.pdf"
    parsed = await extractor.parse_document(file_bytes, filename)
    
    # Check for duplicate in store (same vendor, amount, date)
    for existing in invoices_store:
        if (existing.vendor.lower() == parsed.vendor.lower() and 
            abs(existing.total - parsed.total) < 0.01 and 
            existing.date == parsed.date):
            from .models import AuditFlag
            parsed.audit_flags.append(AuditFlag(
                severity="critical",
                code="DUPLICATE_POTENTIAL",
                title="Potential Duplicate Expense",
                message=f"Matches existing record '{existing.filename}' with identical vendor ({parsed.vendor}), total (${parsed.total:.2f}), and date ({parsed.date}).",
                recommendation="Double check if this invoice was already submitted to avoid double-counting on your tax return."
            ))
            break

    invoices_store.insert(0, parsed)
    return parsed


@app.put("/api/invoices/{invoice_id}", response_model=InvoiceData)
def update_invoice(invoice_id: str, updated: InvoiceData):
    """Update fields on an existing invoice (e.g. user corrections)."""
    for i, inv in enumerate(invoices_store):
        if inv.id == invoice_id:
            # Re-calculate deductible amount
            updated.deductible_amount = round(updated.total * (updated.deductible_percentage / 100.0), 2)
            # Re-run audit checks
            updated.audit_flags = audit_check_invoice(
                vendor=updated.vendor,
                subtotal=updated.subtotal,
                tax=updated.tax,
                total=updated.total,
                date=updated.date or "",
                category=updated.category,
                line_items=updated.line_items
            )
            invoices_store[i] = updated
            return updated
    raise HTTPException(status_code=404, detail="Invoice not found")


@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str):
    global invoices_store
    invoices_store = [inv for inv in invoices_store if inv.id != invoice_id]
    return {"message": "Invoice deleted", "id": invoice_id}


@app.post("/api/invoices/reset-samples")
def reset_samples():
    """Resets the store with fresh sample data."""
    global invoices_store
    invoices_store = [inv.model_copy(deep=True) for inv in SAMPLE_INVOICES]
    return {"message": "Reset to realistic sample invoices", "count": len(invoices_store)}


@app.get("/api/summary", response_model=ExpenseSummary)
def get_summary(tax_rate: float = Query(30.0, ge=10.0, le=50.0)):
    """Computes comprehensive financial and tax analytics."""
    total_spend = sum(inv.total for inv in invoices_store)
    total_deductible = sum(inv.deductible_amount for inv in invoices_store)
    total_tax_paid = sum(inv.tax for inv in invoices_store)
    
    # Calculate tax savings based on marginal freelance tax rate
    tax_savings = round(total_deductible * (tax_rate / 100.0), 2)
    
    # Categories breakdown
    categories: Dict[str, float] = {}
    total_flags = 0
    critical_flags = 0
    
    for inv in invoices_store:
        categories[inv.category] = round(categories.get(inv.category, 0.0) + inv.total, 2)
        total_flags += len(inv.audit_flags)
        critical_flags += sum(1 for f in inv.audit_flags if f.severity == "critical")

    # Risk score assessment
    if critical_flags > 0 or total_flags > len(invoices_store):
        risk = "Moderate" if critical_flags == 0 else "High"
    else:
        risk = "Low"

    return ExpenseSummary(
        total_spend=round(total_spend, 2),
        total_deductible=round(total_deductible, 2),
        total_tax_paid=round(total_tax_paid, 2),
        estimated_tax_savings=tax_savings,
        effective_tax_rate=tax_rate,
        total_documents=len(invoices_store),
        categories_breakdown=categories,
        audit_risk_score=risk,
        flagged_issues_count=total_flags
    )


@app.get("/api/export/csv")
def export_csv():
    """Exports all parsed invoice data as standard CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Invoice ID", "Date", "Vendor", "Invoice #", "Category", 
        "Schedule C Line", "Currency", "Subtotal", "Tax", "Total", 
        "Deductible %", "Deductible Amount", "Business Purpose", "Flags Count"
    ])
    
    for inv in invoices_store:
        writer.writerow([
            inv.id, inv.date, inv.vendor, inv.invoice_number, inv.category,
            inv.schedule_c_line, inv.currency, f"{inv.subtotal:.2f}", f"{inv.tax:.2f}",
            f"{inv.total:.2f}", f"{inv.deductible_percentage}%", f"{inv.deductible_amount:.2f}",
            inv.business_purpose, len(inv.audit_flags)
        ])
        
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ledgerlens_audit_export.csv"}
    )


@app.get("/api/export/report")
def export_report(tax_rate: float = Query(30.0)):
    """Exports an archival Markdown audit and tax filing summary."""
    summary = get_summary(tax_rate=tax_rate)
    
    md = []
    md.append("# 📑 LedgerLens Freelancer Tax & Audit Summary Report")
    md.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    md.append(f"**Audit Risk Rating:** {summary.audit_risk_score} Risk | **Audit Flags Detected:** {summary.flagged_issues_count}\n")
    
    md.append("## 💵 Financial Overview")
    md.append(f"- **Total Gross Spend:** ${summary.total_spend:,.2f}")
    md.append(f"- **Total Tax Deductible (Schedule C):** ${summary.total_deductible:,.2f}")
    md.append(f"- **Total Sales Tax / VAT Paid:** ${summary.total_tax_paid:,.2f}")
    md.append(f"- **Assumed Marginal Tax Rate:** {summary.effective_tax_rate}%")
    md.append(f"- **Estimated Cash Tax Savings:** **${summary.estimated_tax_savings:,.2f}**\n")
    
    md.append("## 📂 Schedule C Category Breakdown")
    md.append("| Category | Total Spent | % of Total Spend |")
    md.append("| :--- | :--- | :--- |")
    for cat, amt in sorted(summary.categories_breakdown.items(), key=lambda x: x[1], reverse=True):
        pct = (amt / summary.total_spend * 100) if summary.total_spend > 0 else 0
        md.append(f"| {cat} | ${amt:,.2f} | {pct:.1f}% |")
    md.append("")
    
    md.append("## 🔍 Itemized Invoices & Verification Flags")
    md.append("| Date | Vendor | Inv # | Category | Total | Deductible | Flags |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for inv in invoices_store:
        flags_text = f"{len(inv.audit_flags)} flags" if inv.audit_flags else "Clean ✓"
        md.append(f"| {inv.date} | {inv.vendor} | {inv.invoice_number} | {inv.category} | ${inv.total:,.2f} | ${inv.deductible_amount:,.2f} | {flags_text} |")
    md.append("")
    
    md.append("> Generated with **LedgerLens** — Privacy-First Open-Source AI Expense Auditor.")
    
    return Response(
        content="\n".join(md),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=ledgerlens_audit_report.md"}
    )


@app.get("/api/settings", response_model=AISettings)
def get_ai_settings():
    return current_settings


@app.post("/api/settings", response_model=AISettings)
def update_ai_settings(settings: AISettings):
    global current_settings, extractor
    current_settings = settings
    extractor = DocumentExtractor(current_settings)
    return current_settings


# Serve static frontend
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>LedgerLens API Running</h1><p>Static index.html not yet initialized.</p>")
