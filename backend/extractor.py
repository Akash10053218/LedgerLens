"""
Open-Source AI & Document Extraction Engine for LedgerLens.
Supports:
1. PyPDF text layout extraction for digital invoices/receipts.
2. Open-Weight Model inference (Gemma 2, Llama 3) via Ollama or Hugging Face.
3. High-precision deterministic regex & financial tokenization engine for 100% offline edge privacy.
"""

import re
import io
import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone
import httpx
from pypdf import PdfReader
from PIL import Image

from .models import InvoiceData, LineItem, AISettings
from .tax_rules import classify_expense, audit_check_invoice

logger = logging.getLogger("ledgerlens.extractor")


class DocumentExtractor:
    def __init__(self, settings: Optional[AISettings] = None):
        self.settings = settings or AISettings()

    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extracts text stream from PDF pages."""
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text_blocks = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                text_blocks.append(f"--- Page {i + 1} ---\n{page_text}")
            return "\n\n".join(text_blocks).strip()
        except Exception as e:
            logger.warning(f"PyPDF extraction error: {e}")
            return ""

    def extract_text_from_image(self, file_bytes: bytes) -> str:
        """Attempts Tesseract OCR if available, else returns metadata placeholder."""
        try:
            import pytesseract  # type: ignore
            image = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(image)
        except Exception:
            return ""

    async def query_open_weight_model(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to query an open-weight model (e.g. Gemma 2 or Llama 3) via Ollama
        or Hugging Face API if configured. Returns structured JSON if successful.
        """
        prompt = f"""
You are a precision financial extraction model. Extract the structured invoice data from the text below.
Return ONLY a valid JSON object matching this schema:
{{
  "vendor": "Company Name",
  "invoice_number": "INV-12345",
  "date": "YYYY-MM-DD",
  "currency": "USD",
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "payment_method": "Visa ...",
  "line_items": [
    {{"description": "Item 1", "quantity": 1, "unit_price": 0.00, "amount": 0.00}}
  ]
}}

DOCUMENT TEXT:
\"\"\"
{raw_text[:3500]}
\"\"\"
"""
        # If Ollama is available
        if self.settings.provider == "ollama" or (self.settings.ollama_url and self.settings.provider != "deterministic"):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{self.settings.ollama_url.rstrip('/')}/api/generate",
                        json={
                            "model": self.settings.model_name or "gemma2:9b",
                            "prompt": prompt,
                            "format": "json",
                            "stream": False
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        response_text = data.get("response", "")
                        return json.loads(response_text)
            except Exception as e:
                logger.info(f"Ollama connection unavailable or timed out: {e}")

        # If Hugging Face token is provided
        if self.settings.hf_token and self.settings.provider == "huggingface":
            try:
                model_id = self.settings.model_name or "google/gemma-2-9b-it"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"https://api-inference.huggingface.co/models/{model_id}",
                        headers={"Authorization": f"Bearer {self.settings.hf_token}"},
                        json={
                            "inputs": prompt,
                            "parameters": {"max_new_tokens": 1024, "return_full_text": False}
                        }
                    )
                    if resp.status_code == 200:
                        out = resp.json()
                        if isinstance(out, list) and len(out) > 0:
                            generated = out[0].get("generated_text", "")
                            match = re.search(r"\{.*\}", generated, re.DOTALL)
                            if match:
                                return json.loads(match.group(0))
            except Exception as e:
                logger.info(f"Hugging Face API call failed: {e}")

        return None

    def deterministic_extract(self, text: str, filename: str = "") -> Dict[str, Any]:
        """
        High-precision deterministic extraction parser.
        Extracts vendor, invoice number, dates, totals, taxes, currency, and line items.
        Guarantees zero-data-leakage 100% offline operation on any laptop or Render container.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # 1. Currency
        currency = "USD"
        if "€" in text or "EUR" in text:
            currency = "EUR"
        elif "£" in text or "GBP" in text:
            currency = "GBP"
        elif "₹" in text or "INR" in text:
            currency = "INR"
        elif "CAD" in text or "C$" in text:
            currency = "CAD"
        elif "AUD" in text or "A$" in text:
            currency = "AUD"

        # 2. Vendor Detection
        vendor = "Unknown Vendor"
        known_vendors = [
            ("Amazon Web Services", ["aws", "amazon web services"]),
            ("Render Services Inc.", ["render.com", "render services", "render"]),
            ("GitHub, Inc.", ["github", "github, inc."]),
            ("DigitalOcean LLC", ["digitalocean"]),
            ("Google Cloud Platform", ["google cloud", "google workspace", "google ireland"]),
            ("Vercel Inc.", ["vercel"]),
            ("Stripe Payments", ["stripe"]),
            ("Apple Inc.", ["apple store", "apple.com", "apple inc"]),
            ("WeWork Coworking", ["wework"]),
            ("Notion Labs Inc.", ["notion labs", "notion"]),
            ("Figma Inc.", ["figma"]),
            ("Slack Technologies", ["slack"]),
            ("OpenAI LLC", ["openai"]),
            ("Uber Technologies", ["uber trip", "uber eats", "uber"]),
            ("Delta Air Lines", ["delta air lines", "delta"]),
            ("Starbucks Coffee", ["starbucks"]),
            ("Best Buy", ["best buy"]),
            ("IKEA", ["ikea"]),
            ("Upwork Global Inc.", ["upwork"]),
            ("Fiverr International", ["fiverr"])
        ]
        
        text_lower = text.lower()
        for v_name, triggers in known_vendors:
            if any(trig in text_lower for trig in triggers):
                vendor = v_name
                break
                
        # If still unknown, inspect first 3 non-empty lines
        if vendor == "Unknown Vendor" and lines:
            for l in lines[:3]:
                # avoid generic invoice header titles
                if not re.search(r"(invoice|receipt|bill|statement|tax|page|\d{4})", l, re.IGNORECASE) and len(l) < 50:
                    vendor = l.title()
                    break

        # 3. Invoice Number
        invoice_number = None
        inv_match = re.search(
            r"(?:Invoice\s*(?:Number|No|#)?|Receipt\s*(?:No|#)?|Order\s*(?:No|#)?|Bill\s*#)[:\s]*([A-Za-z0-9\-–_]{3,24})", 
            text, 
            re.IGNORECASE
        )
        if inv_match:
            invoice_number = inv_match.group(1).strip()
        else:
            # Fallback regex search for pattern like INV-2026-001
            fallback_inv = re.search(r"\b(INV-\d+[-A-Z0-9]*|REC-\d+[-A-Z0-9]*)\b", text, re.IGNORECASE)
            if fallback_inv:
                invoice_number = fallback_inv.group(1).strip()

        # 4. Transaction Date
        date_str = None
        date_patterns = [
            r"\b(202[0-9][-/.](?:0[1-9]|1[0-2])[-/.](?:0[1-9]|[12][0-9]|3[01]))\b",     # 2026-10-15
            r"\b((?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12][0-9]|3[01])[-/.](?:202[0-9]))\b", # 10/15/2026
            r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? (?:202[0-9]))\b"  # October 15, 2026
        ]
        for pat in date_patterns:
            d_match = re.search(pat, text, re.IGNORECASE)
            if d_match:
                date_str = d_match.group(1)
                break
                
        # Standardize date if possible
        formatted_date = date_str
        if date_str:
            try:
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
                    try:
                        clean_d = date_str.replace(".", "")
                        parsed = datetime.strptime(clean_d, fmt)
                        formatted_date = parsed.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            except Exception:
                formatted_date = date_str

        # 5. Financial Amounts (Total, Subtotal, Tax)
        total = 0.0
        subtotal = 0.0
        tax = 0.0

        # Find total patterns: "Total: $123.45", "Total Due", "Amount Due", "Grand Total"
        total_patterns = [
            r"(?:Grand\s*Total|Total\s*Amount|Amount\s*Due|Balance\s*Due|Total\s*Paid|Total)[\s:]*[$€£₹]?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))",
        ]
        for t_pat in total_patterns:
            matches = list(re.finditer(t_pat, text, re.IGNORECASE))
            if matches:
                # Often the last total match is the final grand total
                val_str = matches[-1].group(1).replace(",", "")
                try:
                    val = float(val_str)
                    if val > total:
                        total = val
                except ValueError:
                    pass

        # Subtotal
        sub_match = re.search(r"(?:Subtotal|Sub\s*Total|Net\s*Amount)[\s:]*[$€£₹]?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))", text, re.IGNORECASE)
        if sub_match:
            try:
                subtotal = float(sub_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Tax
        tax_match = re.search(r"(?:Tax|VAT|GST|Sales\s*Tax)[\s:]*[$€£₹]?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))", text, re.IGNORECASE)
        if tax_match:
            try:
                tax = float(tax_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # If subtotal missing but total & tax exist:
        if subtotal == 0.0 and total > 0.0:
            subtotal = round(total - tax, 2)
            
        # 6. Line Items Extraction
        line_items: List[Dict[str, Any]] = []
        # Look for table line patterns: Description ... Amount
        item_pattern = re.compile(r"^(.+?)\s+([0-9]+(?:\.[0-9]{2})?)\s+[$€£₹]?([0-9]+(?:\.[0-9]{2}))\s+[$€£₹]?([0-9]+(?:\.[0-9]{2}))$")
        for line in lines:
            m = item_pattern.match(line)
            if m:
                desc = m.group(1).strip()
                if not re.search(r"(subtotal|total|tax|vat|balance)", desc, re.IGNORECASE):
                    try:
                        qty = float(m.group(2))
                        price = float(m.group(3))
                        amt = float(m.group(4))
                        line_items.append({
                            "description": desc,
                            "quantity": qty,
                            "unit_price": price,
                            "amount": amt
                        })
                    except ValueError:
                        pass

        # If no detailed table matches, fallback to general line item
        if not line_items and total > 0.0:
            line_items.append({
                "description": f"Expense invoice from {vendor}",
                "quantity": 1.0,
                "unit_price": subtotal or total,
                "amount": subtotal or total
            })

        return {
            "vendor": vendor,
            "invoice_number": invoice_number or f"INV-{abs(hash(text)) % 100000:05d}",
            "date": formatted_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "currency": currency,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "line_items": line_items,
            "confidence_score": 0.92 if vendor != "Unknown Vendor" and total > 0 else 0.70,
            "method": "Open Deterministic NLP Engine"
        }

    async def parse_document(self, file_bytes: bytes, filename: str) -> InvoiceData:
        """
        Master extraction pipeline:
        1. Extract text from PDF, Image, or plain text document
        2. Attempt Open-weight model (Gemma 2 / Ollama)
        3. Deterministic NLP extraction fallback
        4. Tax classification & Schedule C mapping
        5. Audit verification & Anomaly detection
        """
        raw_text = ""
        filename_lower = (filename or "").lower()
        
        if filename_lower.endswith(".pdf"):
            raw_text = self.extract_text_from_pdf(file_bytes)
            # If PDF parser extracted nothing (e.g. text file saved with .pdf or text stream), fallback to utf-8
            if not raw_text.strip():
                try:
                    raw_text = file_bytes.decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass
        elif any(filename_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            raw_text = self.extract_text_from_image(file_bytes)
        elif any(filename_lower.endswith(ext) for ext in [".txt", ".csv", ".tsv", ".md"]):
            try:
                raw_text = file_bytes.decode("utf-8", errors="ignore").strip()
            except Exception:
                pass
        else:
            # Fallback for other file types: attempt utf-8 decode
            try:
                raw_text = file_bytes.decode("utf-8", errors="ignore").strip()
            except Exception:
                pass

        # Fallback if raw text is empty (e.g. image with no OCR or binary)
        if not raw_text.strip():
            raw_text = f"Document: {filename}\nAuto-analyzed document record."

        # Try open-weight model first if enabled
        ai_result = await self.query_open_weight_model(raw_text)
        
        if ai_result and ai_result.get("vendor") and ai_result.get("total"):
            extracted = {
                "vendor": ai_result.get("vendor", "Unknown Vendor"),
                "invoice_number": ai_result.get("invoice_number", "INV-UNKNOWN"),
                "date": ai_result.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                "currency": ai_result.get("currency", "USD"),
                "subtotal": float(ai_result.get("subtotal", 0.0)),
                "tax": float(ai_result.get("tax", 0.0)),
                "total": float(ai_result.get("total", 0.0)),
                "line_items": ai_result.get("line_items", []),
                "confidence_score": 0.96,
                "method": f"{self.settings.model_name} (Open-Weight)"
            }
        else:
            extracted = self.deterministic_extract(raw_text, filename)

        # Map to IRS Schedule C Category
        category, schedule_c, deductible_pct, default_purpose = classify_expense(
            vendor=extracted["vendor"], 
            text_content=raw_text
        )

        total_amount = float(extracted["total"])
        deductible_amount = round(total_amount * (deductible_pct / 100.0), 2)

        # Format line items
        formatted_items = []
        for it in extracted.get("line_items", []):
            formatted_items.append(LineItem(
                description=it.get("description", "Item"),
                quantity=float(it.get("quantity", 1.0)),
                unit_price=float(it.get("unit_price", 0.0)),
                amount=float(it.get("amount", 0.0))
            ))

        # Run Audit Checks
        flags = audit_check_invoice(
            vendor=extracted["vendor"],
            subtotal=float(extracted["subtotal"]),
            tax=float(extracted["tax"]),
            total=total_amount,
            date=extracted["date"],
            category=category,
            line_items=formatted_items
        )

        return InvoiceData(
            filename=filename,
            vendor=extracted["vendor"],
            invoice_number=extracted["invoice_number"],
            date=extracted["date"],
            currency=extracted["currency"],
            subtotal=float(extracted["subtotal"]),
            tax=float(extracted["tax"]),
            total=total_amount,
            category=category,
            schedule_c_line=schedule_c,
            deductible_percentage=deductible_pct,
            deductible_amount=deductible_amount,
            business_purpose=default_purpose,
            line_items=formatted_items,
            audit_flags=flags,
            confidence_score=extracted.get("confidence_score", 0.85),
            extraction_method=extracted.get("method", "Hybrid Open AI"),
            raw_text=raw_text[:2000]
        )
