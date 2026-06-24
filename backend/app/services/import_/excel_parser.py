import io
import openpyxl
from typing import List, Dict, Tuple, Any

def parse_excel(content: bytes) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Parse Excel (.xlsx) workbook bytes safely.
    - Max 5MB file size limit.
    - Max 1000 data rows limit.
    - Preserves headers from the first sheet.
    """
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("File size exceeds 5MB limit")
        
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        sheet = wb.active
        if not sheet:
            return [], []
            
        rows = list(sheet.iter_rows(values_only=True))
    except Exception as e:
        raise ValueError(f"Failed to parse Excel workbook: {str(e)}")
    finally:
        try:
            wb.close()
        except Exception:
            pass

    if not rows:
        raise ValueError("Excel sheet has empty or missing header row")
        
    cleaned_rows = []
    for r in rows:
        if any(col is not None and str(col).strip() for col in r):
            cleaned_rows.append(r)
            
    if not cleaned_rows:
        raise ValueError("Excel sheet has empty or missing header row")
        
    headers = [str(h).strip() if h is not None else "" for h in cleaned_rows[0]]
    if not headers or all(not h for h in headers):
        raise ValueError("Excel sheet has empty or missing header row")
        
    data_rows = cleaned_rows[1:]
    
    if len(data_rows) > 1000:
        raise ValueError("Excel contains too many rows (maximum 1000 allowed)")
        
    parsed_data = []
    for r in data_rows:
        row_dict = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            val = str(r[idx]).strip() if idx < len(r) and r[idx] is not None else ""
            row_dict[header] = val
        parsed_data.append(row_dict)
        
    return headers, parsed_data
