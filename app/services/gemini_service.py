import re
import json
import time
import logging
import typing
from datetime import date, datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from app.config import settings

# Setup structured logging
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ParsedOrderItem(BaseModel):
    raw_product_name: str
    quantity: int

class AntigravityParsedOrder(BaseModel):
    items: List[ParsedOrderItem]
    extracted_invoice_preference: typing.Literal["GST_TAX_INVOICE", "RETAIL_INVOICE", "UNSPECIFIED"]

# Preserved for backward compatibility with your other imports
class ParsedOrder(BaseModel):
    items: List[ParsedOrderItem]
    extracted_invoice_preference: typing.Literal["GST_TAX_INVOICE", "RETAIL_INVOICE", "UNSPECIFIED"]


class PaymentPromiseExtraction(BaseModel):
    is_payment_promise: bool
    # ISO format (YYYY-MM-DD) resolved against the supplied reference date, or None
    # when no promise / no discernible date was found.
    promised_date: Optional[str] = None
    promised_amount: Optional[float] = None

# ---------------------------------------------------------------------------
# Core Service
# ---------------------------------------------------------------------------

class GeminiService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            try:
                genai.configure(api_key=self.api_key)
                # Using gemini-2.5-flash for rapid, cost-effective NLP parsing
                self.model = genai.GenerativeModel("gemini-2.5-flash")
                logger.info("Gemini Service initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
                self.enabled = False
        else:
            logger.warning("Gemini API key not found. Running strictly in Regex Fallback mode.")

    def parse_order_text(self, text: str) -> AntigravityParsedOrder:
        """
        Parses unstructured text (Hindi/English/Hinglish) into a structured list of items.
        Wraps the API call in an exponential backoff loop to protect against transient Google 500 errors.
        """
        if not text.strip():
            return AntigravityParsedOrder(items=[], extracted_invoice_preference="UNSPECIFIED")

        if self.enabled:
            prompt = (
                "You are a sales order parsing assistant for Indian B2B FMCG distributors. "
                "Parse the following order message written in English, Hindi, or Hinglish. "
                "Extract each product name (including brand if mentioned) and its precise quantity. "
                "Also, scan colloquial business language phrases to classify the invoice preference:\n"
                "- If the message contains expressions like 'GST lagana', 'tax invoice', 'GST bill', 'with tax', 'Company ka bill', 'GST number', set extracted_invoice_preference to 'GST_TAX_INVOICE'.\n"
                "- If the message contains expressions like 'normal bill', 'cash bill', 'bina tax', 'kachha bill', 'bina GST', 'kachha', set extracted_invoice_preference to 'RETAIL_INVOICE'.\n"
                "- If no specific invoice preference is requested, set extracted_invoice_preference to 'UNSPECIFIED'.\n"
                "Return the data strictly as JSON matching the schema."
            )

            generation_config = {
                "response_mime_type": "application/json",
                "response_schema": AntigravityParsedOrder,
            }

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(
                        contents=[prompt, f"Order Message: {text}"],
                        generation_config=generation_config
                    )
                    
                    parsed_json = json.loads(response.text)
                    if "extracted_invoice_preference" not in parsed_json:
                        parsed_json["extracted_invoice_preference"] = "UNSPECIFIED"
                    return AntigravityParsedOrder(**parsed_json)

                except (google_exceptions.InternalServerError, 
                        google_exceptions.ServiceUnavailable, 
                        google_exceptions.TooManyRequests) as transient_err:
                    
                    # Catch transient cloud errors (like ESF 500) and implement exponential backoff
                    logger.warning(f"Google Cloud Transient Error (Attempt {attempt + 1}/{max_retries}): {transient_err}")
                    
                    if attempt == max_retries - 1:
                        logger.error("Max retries reached for Gemini API. Gracefully degrading to regex parser.")
                        break  # Exit loop and fall back
                        
                    # Backoff: 1s -> 2s -> Give up
                    time.sleep(2 ** attempt)

                except json.JSONDecodeError as json_err:
                    # Model hallucinated invalid JSON structure (unlikely with response_schema, but safe)
                    logger.error(f"Gemini returned malformed JSON: {json_err}. Falling back.")
                    break
                    
                except Exception as fatal_err:
                    # Hard failures (e.g. Invalid API Key, 400 Bad Request). Do not waste time retrying.
                    logger.error(f"Fatal Gemini API parsing error: {fatal_err}. Falling back to regex parser immediately.")
                    break

        # Fallback executed if API is disabled, out of retries, or experiences a hard fault
        return self._fallback_regex_parser(text)

    def extract_payment_promise(self, text: str, reference_date: Optional[datetime] = None) -> PaymentPromiseExtraction:
        """
        Extracts a payment promise (e.g. "I'll pay by Friday", "will clear
        the bill tomorrow", "paying 5000 next week") from a free-text inbound
        WhatsApp reply. `reference_date` anchors relative dates like
        "tomorrow"/"Friday" (defaults to now). Never raises — falls back to a
        narrow regex parser on any AI failure, same resilience pattern as
        parse_order_text.
        """
        ref = reference_date or datetime.utcnow()

        if not text.strip():
            return PaymentPromiseExtraction(is_payment_promise=False)

        if self.enabled:
            prompt = (
                "You are analysing an inbound WhatsApp reply from a retailer to their FMCG "
                "distributor, written in English, Hindi, or Hinglish. Determine whether this "
                "message contains a promise to pay an outstanding bill (e.g. 'I'll pay by Friday', "
                "'paisa kal de dunga', 'will clear next week', 'paying 5000 on Monday'). "
                f"Today's date is {ref.date().isoformat()} ({ref.strftime('%A')}). "
                "If it is a payment promise, resolve any relative date reference (e.g. 'Friday', "
                "'tomorrow', 'next week') into an absolute ISO date (YYYY-MM-DD) using today's date "
                "as the anchor, and extract a promised amount in rupees if one is explicitly mentioned "
                "(otherwise leave it null). If the message is not a payment promise at all (e.g. it's "
                "a new order, a general question, or irrelevant chit-chat), set is_payment_promise to "
                "false and leave the other fields null. Return the data strictly as JSON matching the schema."
            )

            generation_config = {
                "response_mime_type": "application/json",
                "response_schema": PaymentPromiseExtraction,
            }

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(
                        contents=[prompt, f"Message: {text}"],
                        generation_config=generation_config
                    )
                    parsed_json = json.loads(response.text)
                    return PaymentPromiseExtraction(**parsed_json)

                except (google_exceptions.InternalServerError,
                        google_exceptions.ServiceUnavailable,
                        google_exceptions.TooManyRequests) as transient_err:
                    logger.warning(f"Google Cloud Transient Error on promise extraction (Attempt {attempt + 1}/{max_retries}): {transient_err}")
                    if attempt == max_retries - 1:
                        logger.error("Max retries reached for Gemini promise extraction. Falling back to regex parser.")
                        break
                    time.sleep(2 ** attempt)

                except json.JSONDecodeError as json_err:
                    logger.error(f"Gemini returned malformed JSON for promise extraction: {json_err}. Falling back.")
                    break

                except Exception as fatal_err:
                    logger.error(f"Fatal Gemini API error during promise extraction: {fatal_err}. Falling back to regex parser immediately.")
                    break

        return self._fallback_regex_promise_parser(text, ref)

    def _fallback_regex_promise_parser(self, text: str, ref: datetime) -> PaymentPromiseExtraction:
        """
        Narrow, conservative regex fallback for payment-promise detection.
        Only fires for a small set of unambiguous "pay" + relative-date
        phrases — intentionally does not try to handle every phrasing Gemini
        would catch; false negatives here just mean no promise gets logged,
        which is safe (no incorrect data is ever persisted).
        """
        lowered = text.lower()

        pay_keywords = ["pay", "paisa", "payment", "clear", "settle", "bill de", "paise"]
        if not any(kw in lowered for kw in pay_keywords):
            return PaymentPromiseExtraction(is_payment_promise=False)

        weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        promised_date: Optional[date] = None

        if "tomorrow" in lowered or "kal" in lowered:
            promised_date = (ref + timedelta(days=1)).date()
        elif "today" in lowered or "aaj" in lowered:
            promised_date = ref.date()
        elif "next week" in lowered:
            promised_date = (ref + timedelta(days=7)).date()
        else:
            for idx, day_name in enumerate(weekday_names):
                if day_name in lowered:
                    days_ahead = (idx - ref.weekday()) % 7
                    days_ahead = days_ahead or 7  # if today is that weekday, assume next occurrence
                    promised_date = (ref + timedelta(days=days_ahead)).date()
                    break

        if promised_date is None:
            # A "pay" keyword with no resolvable date is too ambiguous to log as a promise.
            return PaymentPromiseExtraction(is_payment_promise=False)

        amount_match = re.search(r"(?:rs\.?|₹|inr)\s?([\d,]+(?:\.\d+)?)", lowered)
        promised_amount = None
        if amount_match:
            try:
                promised_amount = float(amount_match.group(1).replace(",", ""))
            except ValueError:
                promised_amount = None

        return PaymentPromiseExtraction(
            is_payment_promise=True,
            promised_date=promised_date.isoformat(),
            promised_amount=promised_amount,
        )

    def _fallback_regex_parser(self, text: str) -> AntigravityParsedOrder:
        """
        Rule-based parser using regex to extract numbers and surrounding words.
        Provides zero-downtime resilience when LLM services are unavailable.
        """
        normalized = text.lower()
        items = []

        # Extract invoice preference from colloquial phrases
        extracted_pref = "UNSPECIFIED"
        if any(phrase in normalized for phrase in ["normal bill", "cash bill", "bina tax", "kachha", "bina gst"]):
            extracted_pref = "RETAIL_INVOICE"
        elif any(phrase in normalized for phrase in ["gst lagana", "tax invoice", "gst bill", "tax bill", "company ka bill", "gst number", "gst invoice"]):
            extracted_pref = "GST_TAX_INVOICE"

        # General regex matching mapping
        matches = re.finditer(r'(\d+)\s*(?:packets?|pkts?|bags?|kg|liters?|pcs?|units?|box)?\s+([A-Za-z0-9\s\u0900-\u097F]{3,20})', text, re.IGNORECASE)
        for match in matches:
            qty = int(match.group(1))
            item_name = match.group(2).strip()
            # Clean up item_name by removing trailing connectors
            item_name = re.sub(r'\b(aur|and|with|chahiye|lene|laya|box|packets?)\b.*$', '', item_name, flags=re.IGNORECASE).strip()
            if len(item_name) >= 3:
                items.append(ParsedOrderItem(raw_product_name=item_name, quantity=qty))

        return AntigravityParsedOrder(items=items, extracted_invoice_preference=extracted_pref)
