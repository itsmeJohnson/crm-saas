import difflib
from typing import List, Dict, Any

STANDARD_FIELDS = {
    "first_name": ["first name", "given name", "fname", "first"],
    "last_name": ["last name", "surname", "lname", "last"],
    "email": ["email", "email address", "mail", "email_address"],
    "phone": ["phone", "telephone", "phone number", "mobile", "phone_number"],
    "company_name": ["company", "organization", "org", "company name", "company_name"],
    "title": ["title", "job title", "position", "role", "job_title"],
    "source": ["source", "lead source", "lead_source", "channel"],
    "status": ["status", "lead status", "lead_status"],
    "assigned_email": ["assigned email", "assigned_email", "owner email", "owner_email", "assigned user", "assigned_user"]
}

def clean_string(s: str) -> str:
    return s.strip().lower().replace("_", " ").replace("-", " ")

def calculate_confidence(header: str, field_name: str) -> int:
    """
    Calculate confidence score (0 to 100) for a header matching a field name.
    100 = Exact match
    80 = Alias match
    60 = Fuzzy match (similarity >= 0.7)
    0 = No match
    """
    header_clean = clean_string(header)
    field_clean = clean_string(field_name)
    
    # 1. Exact match
    if header_clean == field_clean:
        return 100
        
    # 2. Alias match
    aliases = STANDARD_FIELDS.get(field_name, [])
    for alias in aliases:
        if header_clean == clean_string(alias):
            return 80
            
    # 3. Fuzzy match
    ratio = difflib.SequenceMatcher(None, header_clean, field_clean).ratio()
    if ratio >= 0.7:
        return 60
        
    for alias in aliases:
        ratio = difflib.SequenceMatcher(None, header_clean, clean_string(alias)).ratio()
        if ratio >= 0.7:
            return 60
            
    return 0

def suggest_mappings(headers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Suggest mappings for standard fields from a list of headers.
    Returns: {field_name: {"column": header | None, "confidence": score}}
    Ensures each header is only mapped once.
    """
    suggestions = {}
    used_headers = set()
    
    for field_name in STANDARD_FIELDS.keys():
        best_header = None
        best_score = 0
        
        for header in headers:
            if header in used_headers:
                continue
            score = calculate_confidence(header, field_name)
            if score > best_score:
                best_score = score
                best_header = header
                
        if best_score > 0 and best_header is not None:
            suggestions[field_name] = {"column": best_header, "confidence": best_score}
            used_headers.add(best_header)
        else:
            suggestions[field_name] = {"column": None, "confidence": 0}
            
    return suggestions
