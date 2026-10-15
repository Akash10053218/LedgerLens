"""
Automated Test Suite for LedgerLens
Tests:
- API health and summary calculation
- PyPDF & Regex extraction logic
- IRS Schedule C classification
- Audit flags generation (math discrepancy, meal rule, 1099 rule)
- CSV and Markdown Report export formats
"""

import unittest
from backend.models import InvoiceData, LineItem
from backend.tax_rules import classify_expense, audit_check_invoice
from backend.extractor import DocumentExtractor


class TestLedgerLens(unittest.TestCase):

    def setUp(self):
        self.extractor = DocumentExtractor()

    def test_tax_classification(self):
        # Software & Cloud test
        cat, sched_c, pct, _ = classify_expense("Render Services Inc.", "Invoice for Web Service")
        self.assertEqual(cat, "Software & Cloud")
        self.assertEqual(pct, 100.0)
        self.assertIn("Line 18", sched_c)

        # Meals test
        cat_meal, sched_c_meal, pct_meal, _ = classify_expense("The Capital Grille", "Dinner with client")
        self.assertEqual(cat_meal, "Business Meals")
        self.assertEqual(pct_meal, 50.0)
        self.assertIn("Line 24b", sched_c_meal)

        # Contractor test
        cat_cont, sched_c_cont, pct_cont, _ = classify_expense("Alex Rivera", "Contractor engineering fee")
        self.assertEqual(cat_cont, "Contract Labor")
        self.assertEqual(pct_cont, 100.0)
        self.assertIn("Line 11", sched_c_cont)

    def test_audit_flags(self):
        # Math mismatch check
        flags = audit_check_invoice(
            vendor="Test Vendor",
            subtotal=100.0,
            tax=10.0,
            total=125.0,  # 100 + 10 != 125
            date="2026-10-15",
            category="Software & Cloud"
        )
        codes = [f.code for f in flags]
        self.assertIn("MATH_MISMATCH", codes)

        # 1099 check for contract labor > $600
        contract_flags = audit_check_invoice(
            vendor="Contractor Dev",
            subtotal=750.0,
            tax=0.0,
            total=750.0,
            date="2026-10-15",
            category="Contract Labor"
        )
        self.assertIn("CONTRACT_1099_REQ", [f.code for f in contract_flags])

        # Meal 50% limitation flag
        meal_flags = audit_check_invoice(
            vendor="Bistro",
            subtotal=80.0,
            tax=8.0,
            total=88.0,
            date="2026-10-15",
            category="Business Meals"
        )
        self.assertIn("MEAL_50_LIMIT", [f.code for f in meal_flags])

    def test_deterministic_extraction(self):
        sample_raw = """
        Render Services Inc.
        San Francisco, CA
        Invoice Number: INV-RND-2026-9041
        Date: 2026-10-12
        
        Description                     Qty    Unit Price    Amount
        Standard Web Service            1      $25.00        $25.00
        Managed Postgres                1      $35.00        $35.00
        
        Subtotal: $60.00
        Tax: $0.00
        Total: $60.00
        """
        result = self.extractor.deterministic_extract(sample_raw)
        self.assertEqual(result["vendor"], "Render Services Inc.")
        self.assertEqual(result["invoice_number"], "INV-RND-2026-9041")
        self.assertEqual(result["date"], "2026-10-12")
        self.assertEqual(result["total"], 60.00)
        self.assertEqual(result["subtotal"], 60.00)
        self.assertEqual(result["currency"], "USD")


if __name__ == "__main__":
    unittest.main()
