import csv
import io
from typing import List, Dict, Tuple, Any

def parse_csv(content: bytes) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Parse CSV bytes safely under strict constraints.
    - Max 5MB file size.
    - Max 1000 data rows.
    - Delimiter auto-detection.
    - Multi-encoding fallback.
    """
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("File size exceeds 5MB limit")
        
    decoded_content = ""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            decoded_content = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not decoded_content:
        raise ValueError("Failed to decode CSV content. Unsupported encoding.")
        
    delimiter = ","
    try:
        sample = decoded_content[:1024]
        if sample:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=",\t;|")
            delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    f = io.StringIO(decoded_content)
    try:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV content: {str(e)}")

    if not rows:
        raise ValueError("CSV file has empty or missing header row")
        
    cleaned_rows = [r for r in rows if any(col.strip() for col in r)]
    if not cleaned_rows:
        raise ValueError("CSV file has empty or missing header row")
        
    headers = [h.strip() for h in cleaned_rows[0]]
    if not headers or all(not h for h in headers):
        raise ValueError("CSV file has empty or missing header row")
        
    data_rows = cleaned_rows[1:]
    
    if len(data_rows) > 1000:
        raise ValueError("CSV contains too many rows (maximum 1000 allowed)")
        
    parsed_data = []
    for r in data_rows:
        row_dict = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            val = r[idx].strip() if idx < len(r) else ""
            row_dict[header] = val
        parsed_data.append(row_dict)
        
    return headers, parsed_data
