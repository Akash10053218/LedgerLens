"""
Tax classification rules and audit anomaly heuristics for LedgerLens.
Encodes IRS Schedule C deductibility logic, business expense classifications,
and compliance checks.
"""

from typing import Tuple, List, Dict, Any
from .models import AuditFlag


TAX_CATEGORIES = {
    "Software & Cloud": {
        "schedule_c_line": "Line 18: Office expense (Software/SaaS)",
        "deductible_percentage": 100.0,
        "keywords": [
            "aws", "amazon web services", "render", "digitalocean", "vultr", "github", 
            "gitlab", "vercel", "netlify", "google cloud", "gcp", "azure", "openai", 
            "anthropic", "hugging face", "cloudflare", "datadog", "sentry", "notion", 
            "slack", "zoom", "adobe", "figma", "jetbrains", "stripe", "canva", "linear"
        ],
        "default_purpose": "Cloud hosting and developer tooling infrastructure"
    },
    "Advertising & Marketing": {
        "schedule_c_line": "Line 8: Advertising",
        "deductible_percentage": 100.0,
        "keywords": [
            "google ads", "meta ads", "facebook ads", "linkedin", "twitter", "x ads",
            "tiktok", "mailchimp", "substack", "beehiiv", "convertkit", "domain", 
            "godaddy", "namecheap", "sponsorship", "marketing", "promotion", "pr release"
        ],
        "default_purpose": "Client acquisition and commercial brand marketing"
    },
    "Travel & Lodging": {
        "schedule_c_line": "Line 24a: Travel",
        "deductible_percentage": 100.0,
        "keywords": [
            "airline", "airways", "delta", "united", "american airlines", "southwest",
            "hotel", "marriott", "hilton", "airbnb", "hyatt", "amtrak", "train",
            "car rental", "hertz", "enterprise", "lyft", "uber", "flight"
        ],
        "default_purpose": "Business client visit and on-site conference travel"
    },
    "Business Meals": {
        "schedule_c_line": "Line 24b: Deductible meals (50%)",
        "deductible_percentage": 50.0,
        "keywords": [
            "restaurant", "cafe", "coffee", "starbucks", "doordash", "ubereats", 
            "grubhub", "bistro", "diner", "pizza", "catering", "bakery", "bar & grill",
            "grill", "grille", "dinner", "lunch", "breakfast", "food", "steakhouse", "eatery"
        ],
        "default_purpose": "Business meal discussion with clients/contractors (50% deductible)"
    },
    "Contract Labor": {
        "schedule_c_line": "Line 11: Contract labor",
        "deductible_percentage": 100.0,
        "keywords": [
            "upwork", "fiverr", "freelancer", "contractor", "subcontractor", "consultant",
            "consulting fee", "development services", "design services", "toptal"
        ],
        "default_purpose": "Independent 1099 subcontractor engineering/design labor"
    },
    "Office Supplies & Equipment": {
        "schedule_c_line": "Line 18: Office expense",
        "deductible_percentage": 100.0,
        "keywords": [
            "apple", "best buy", "staples", "office depot", "ikea", "herman miller",
            "micro center", "keyboard", "monitor", "laptop", "mouse", "desk", "printer",
            "b&h photo", "hardware"
        ],
        "default_purpose": "Office workstation hardware and ergonomic gear"
    },
    "Legal & Professional Services": {
        "schedule_c_line": "Line 17: Legal and professional services",
        "deductible_percentage": 100.0,
        "keywords": [
            "attorney", "law firm", "cpa", "accounting", "bookkeeping", "tax prep",
            "legalzoom", "registered agent", "audit fee", "notary"
        ],
        "default_purpose": "Corporate legal counsel, bookkeeping, and tax compliance"
    },
    "Utilities & Internet": {
        "schedule_c_line": "Line 25: Utilities",
        "deductible_percentage": 100.0,
        "keywords": [
            "verizon", "at&t", "t-mobile", "comcast", "xfinity", "spectrum",
            "internet", "broadband", "mobile phone", "electric", "power"
        ],
        "default_purpose": "High-speed business fiber internet and mobile connectivity"
    },
    "Education & Training": {
        "schedule_c_line": "Line 27a: Other expenses (Education)",
        "deductible_percentage": 100.0,
        "keywords": [
            "coursera", "udemy", "oreilly", "pluralsight", "book", "textbook",
            "conference ticket", "workshop", "certification", "training", "tutorial"
        ],
        "default_purpose": "Professional skills maintenance and technical training"
    }
}


def classify_expense(vendor: str, text_content: str = "") -> Tuple[str, str, float, str]:
    """
    Classifies an invoice into IRS Schedule C category based on vendor and text.
    Returns (category_name, schedule_c_line, deductible_percentage, default_purpose).
    """
    combined = f"{vendor.lower()} {text_content.lower()}"
    
    for category_name, data in TAX_CATEGORIES.items():
        for keyword in data["keywords"]:
            if keyword in combined:
                return (
                    category_name,
                    data["schedule_c_line"],
                    data["deductible_percentage"],
                    data["default_purpose"]
                )
                
    # Fallback default
    return (
        "General Business Expense",
        "Line 27a: Other expenses",
        100.0,
        "Ordinary and necessary freelance operational expense"
    )


def audit_check_invoice(
    vendor: str,
    subtotal: float,
    tax: float,
    total: float,
    date: str,
    category: str,
    line_items: list = None
) -> List[AuditFlag]:
    """
    Evaluates an invoice against standard freelance audit heuristics and IRS rules.
    """
    flags: List[AuditFlag] = []
    
    # Check 1: Math Verification
    if subtotal > 0 and total > 0:
        expected_total = round(subtotal + tax, 2)
        diff = abs(expected_total - round(total, 2))
        if diff > 0.08:
            flags.append(AuditFlag(
                severity="critical" if diff > 1.0 else "warning",
                code="MATH_MISMATCH",
                title="Subtotal / Tax Discrepancy",
                message=f"Extracted subtotal ({subtotal:.2f}) + tax ({tax:.2f}) = {expected_total:.2f}, which does not match total ({total:.2f}).",
                recommendation="Verify invoice line items or discount/tip inclusions manually before filing."
            ))
            
    # Check 2: IRS $75 Document Archiving Threshold
    if total >= 75.0:
        flags.append(AuditFlag(
            severity="info",
            code="IRS_RECEIPT_REQ",
            title="Receipt Archiving Required (> $75)",
            message=f"IRS Regulation 1.274-5 requires strict documentary proof (digital receipt/invoice) for expenses of $75 or more.",
            recommendation="LedgerLens has saved and indexed this document. Keep in archival records for 3 years."
        ))
        
    # Check 3: Capitalization vs Expensing Threshold ($2,500 De Minimis)
    if total >= 2500.0:
        flags.append(AuditFlag(
            severity="warning",
            code="DE_MINIMIS_LIMIT",
            title="Asset Capitalization Check (> $2,500)",
            message=f"This single purchase is {total:.2f}, which reaches the IRS De Minimis Safe Harbor limit ($2,500).",
            recommendation="Confirm whether this is a recurring service or tangible capital property that requires depreciation or Section 179 expensing."
        ))
        
    # Check 4: 50% Meal Limitation
    if category == "Business Meals":
        flags.append(AuditFlag(
            severity="warning",
            code="MEAL_50_LIMIT",
            title="50% Meal Deduction Rule",
            message="Business meals are limited to a 50% deduction under IRC § 274(n).",
            recommendation="Maintain notes of business purpose and persons present to substantiate deduction."
        ))
        
    # Check 5: 1099-NEC Threshold for Contractors
    if category == "Contract Labor" and total >= 600.0:
        flags.append(AuditFlag(
            severity="warning",
            code="CONTRACT_1099_REQ",
            title="Form 1099-NEC Requirement (> $600)",
            message=f"Cumulative payments of $600 or more to an unincorporated US contractor require filing Form 1099-NEC by January 31.",
            recommendation="Collect a signed Form W-9 from this vendor if not already on file."
        ))
        
    # Check 6: Missing Date
    if not date or date.strip() == "":
        flags.append(AuditFlag(
            severity="warning",
            code="MISSING_DATE",
            title="Missing Transaction Date",
            message="The invoice does not have an easily detectable transaction date.",
            recommendation="Assign the correct tax year and calendar date for proper deduction timing."
        ))
        
    return flags
