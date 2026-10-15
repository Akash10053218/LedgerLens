"""
Sample realistic invoices for 1-click testing and initial state.
Covers diverse freelance scenarios: Cloud hosting (Render), Equipment,
Client meals (50% rule), Subcontractor (1099-NEC alert), and Travel.
"""

from typing import List
from .models import InvoiceData, LineItem, AuditFlag

SAMPLE_INVOICES: List[InvoiceData] = [
    InvoiceData(
        id="inv-sample-001",
        filename="render-cloud-october-2026.pdf",
        vendor="Render Services Inc.",
        invoice_number="INV-RND-89410",
        date="2026-10-10",
        due_date="2026-10-10",
        currency="USD",
        subtotal=85.00,
        tax=0.00,
        total=85.00,
        payment_method="Mastercard *8819",
        category="Software & Cloud",
        schedule_c_line="Line 18: Office expense (Software/SaaS)",
        deductible_percentage=100.0,
        deductible_amount=85.00,
        business_purpose="Production web service hosting and Postgres instance on Render",
        line_items=[
            LineItem(description="Starter Web Service (0.5 CPU, 512MB RAM)", quantity=1.0, unit_price=7.00, amount=7.00),
            LineItem(description="Managed PostgreSQL Database (Standard Tier)", quantity=1.0, unit_price=35.00, amount=35.00),
            LineItem(description="Render Pro Workspace Developer Seats", quantity=1.0, unit_price=43.00, amount=43.00)
        ],
        audit_flags=[
            AuditFlag(
                severity="info",
                code="IRS_RECEIPT_REQ",
                title="Receipt Archiving Required (> $75)",
                message="IRS Regulation 1.274-5 requires strict documentary proof for expenses of $75 or more.",
                recommendation="Document indexed in LedgerLens archival storage."
            )
        ],
        confidence_score=0.98,
        extraction_method="Gemma-2-9b Open Model",
        raw_text="Render Services Inc. Invoice #INV-RND-89410 Date: 2026-10-10 Total: $85.00"
    ),
    InvoiceData(
        id="inv-sample-002",
        filename="alex-rivera-frontend-contractor.pdf",
        vendor="Alex Rivera Design LLC",
        invoice_number="INV-2026-088",
        date="2026-10-04",
        due_date="2026-10-18",
        currency="USD",
        subtotal=850.00,
        tax=0.00,
        total=850.00,
        payment_method="Direct Bank Wire (ACH)",
        category="Contract Labor",
        schedule_c_line="Line 11: Contract labor",
        deductible_percentage=100.0,
        deductible_amount=850.00,
        business_purpose="Contract frontend engineer sub-development for client mobile application",
        line_items=[
            LineItem(description="Figma to Tailwind CSS component implementation", quantity=17.0, unit_price=50.00, amount=850.00)
        ],
        audit_flags=[
            AuditFlag(
                severity="warning",
                code="CONTRACT_1099_REQ",
                title="Form 1099-NEC Requirement (> $600)",
                message="Cumulative payments of $600 or more to an unincorporated US contractor require Form 1099-NEC.",
                recommendation="Ensure W-9 is signed and filed before Jan 31 tax deadline."
            ),
            AuditFlag(
                severity="info",
                code="IRS_RECEIPT_REQ",
                title="Receipt Archiving Required (> $75)",
                message="IRS receipt archiving threshold met.",
                recommendation="Saved in permanent records."
            )
        ],
        confidence_score=0.95,
        extraction_method="Deterministic Open Parser",
        raw_text="Alex Rivera Design LLC Invoice #INV-2026-088 Date: 2026-10-04 Subtotal: $850.00 Total: $850.00"
    ),
    InvoiceData(
        id="inv-sample-003",
        filename="client-closing-dinner-bistro.png",
        vendor="The Capital Grille & Bistro",
        invoice_number="REC-CG-7729",
        date="2026-10-08",
        due_date="2026-10-08",
        currency="USD",
        subtotal=125.00,
        tax=11.00,
        total=148.50,  # includes tip
        payment_method="Visa *4242",
        category="Business Meals",
        schedule_c_line="Line 24b: Deductible meals (50%)",
        deductible_percentage=50.0,
        deductible_amount=74.25,
        business_purpose="Dinner with prospective client partner discussing Q4 contract scope",
        line_items=[
            LineItem(description="Client Dinner Entrees (2x)", quantity=2.0, unit_price=45.00, amount=90.00),
            LineItem(description="Beverages & Espresso", quantity=2.0, unit_price=17.50, amount=35.00),
            LineItem(description="Sales Tax & Gratuity", quantity=1.0, unit_price=23.50, amount=23.50)
        ],
        audit_flags=[
            AuditFlag(
                severity="warning",
                code="MEAL_50_LIMIT",
                title="50% Meal Deduction Rule",
                message="Business meals are strictly limited to a 50% tax deduction under IRC § 274(n).",
                recommendation="Keep written note of attendees: 'Jane Smith, VP Eng Acme Corp'."
            )
        ],
        confidence_score=0.91,
        extraction_method="SmolVLM Open OCR Vision",
        raw_text="The Capital Grille & Bistro Receipt REC-CG-7729 Date: 2026-10-08 Total: $148.50"
    ),
    InvoiceData(
        id="inv-sample-004",
        filename="delta-airlines-pycon-travel.pdf",
        vendor="Delta Air Lines",
        invoice_number="TKT-0062491823",
        date="2026-09-28",
        due_date="2026-09-28",
        currency="USD",
        subtotal=445.00,
        tax=37.20,
        total=482.20,
        payment_method="Amex *1004",
        category="Travel & Lodging",
        schedule_c_line="Line 24a: Travel",
        deductible_percentage=100.0,
        deductible_amount=482.20,
        business_purpose="Round-trip airfare to PyCon tech developer conference",
        line_items=[
            LineItem(description="Round-trip Main Cabin Flight JFK -> SLC", quantity=1.0, unit_price=445.00, amount=445.00),
            LineItem(description="Federal Transportation & Passenger Facility Tax", quantity=1.0, unit_price=37.20, amount=37.20)
        ],
        audit_flags=[
            AuditFlag(
                severity="info",
                code="IRS_RECEIPT_REQ",
                title="Receipt Archiving Required (> $75)",
                message="IRS receipt archiving threshold met.",
                recommendation="Keep boarding passes with travel records."
            )
        ],
        confidence_score=0.97,
        extraction_method="PyPDF Layout Analyzer",
        raw_text="Delta Air Lines E-Ticket TKT-0062491823 Date: 2026-09-28 Total: $482.20"
    ),
    InvoiceData(
        id="inv-sample-005",
        filename="apple-mac-studio-monitor.pdf",
        vendor="Apple Inc.",
        invoice_number="INV-APL-2026-442",
        date="2026-10-01",
        due_date="2026-10-01",
        currency="USD",
        subtotal=1499.00,
        tax=134.91,
        total=1633.91,
        payment_method="Apple Card *9921",
        category="Office Supplies & Equipment",
        schedule_c_line="Line 18: Office expense",
        deductible_percentage=100.0,
        deductible_amount=1633.91,
        business_purpose="Studio Display monitor for coding and design workstation",
        line_items=[
            LineItem(description="Apple Studio Display (Standard Glass)", quantity=1.0, unit_price=1499.00, amount=1499.00),
            LineItem(description="State & Local Sales Tax", quantity=1.0, unit_price=134.91, amount=134.91)
        ],
        audit_flags=[
            AuditFlag(
                severity="info",
                code="IRS_RECEIPT_REQ",
                title="Receipt Archiving Required (> $75)",
                message="IRS receipt archiving threshold met.",
                recommendation="Retain warranty and invoice."
            )
        ],
        confidence_score=0.99,
        extraction_method="Gemma-2-9b Open Model",
        raw_text="Apple Inc. Invoice INV-APL-2026-442 Date: 2026-10-01 Subtotal: $1499.00 Tax: $134.91 Total: $1633.91"
    )
]
