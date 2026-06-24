import re
from typing import List, Dict, Any, Callable, Awaitable, Tuple

EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

def normalize_phone(phone: str) -> str:
    """Normalize phone number to digits and + symbol only."""
    if not phone:
        return ""
    return re.sub(r"[^\d+]", "", phone)

async def validate_import_rows(
    rows: List[Dict[str, str]],
    column_mapping: Dict[str, str],
    check_existing_email_fn: Callable[[str], Awaitable[bool]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate mapped rows.
    Returns: Tuple of (valid_rows_list, errors_list)
    """
    errors = []
    valid_rows = []
    seen_emails_in_batch = set()
    
    for idx, row in enumerate(rows, start=2):
        row_errors = []
        
        mapped_values = {}
        for std_field in ["first_name", "last_name", "email", "phone", "company_name", "title", "source", "status", "assigned_email", "city"]:
            col_name = column_mapping.get(std_field)
            val = row.get(col_name, "").strip() if col_name else ""
            mapped_values[std_field] = val

        last_name = mapped_values.get("last_name", "")
        title = mapped_values.get("title", "")
        email = mapped_values.get("email", "")
        phone = mapped_values.get("phone", "")
        
        # Check Required Columns
        if not last_name:
            row_errors.append("Last Name is a required field and is missing")
        if not title:
            row_errors.append("Job Title/Lead Title is a required field and is missing")
            
        # Check Max Lengths
        lengths_config = {
            "first_name": 100,
            "last_name": 100,
            "email": 255,
            "phone": 50,
            "company_name": 255,
            "title": 255,
            "source": 100,
            "status": 50,
            "assigned_email": 255,
            "city": 100
        }
        for field, max_len in lengths_config.items():
            val = mapped_values.get(field, "")
            if val and len(val) > max_len:
                row_errors.append(f"{field.replace('_', ' ').title()} exceeds maximum length of {max_len} characters")
                
        # Check Email Format & Duplicates
        if email:
            if not re.match(EMAIL_REGEX, email):
                row_errors.append("Invalid email address format")
            else:
                email_lower = email.lower()
                if email_lower in seen_emails_in_batch:
                    row_errors.append("Duplicate email address found within this import batch")
                else:
                    seen_emails_in_batch.add(email_lower)
                    is_dup = await check_existing_email_fn(email_lower)
                    if is_dup:
                        row_errors.append("Lead with email already exists in your organization")

        if row_errors:
            errors.append({
                "row": idx,
                "email": email or None,
                "reason": "; ".join(row_errors)
            })
        else:
            if phone:
                mapped_values["phone"] = normalize_phone(phone)
            valid_rows.append({
                "row_index": idx,
                "data": mapped_values
            })
            
    return valid_rows, errors
