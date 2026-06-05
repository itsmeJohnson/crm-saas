import re
import httpx

def normalize_google_sheets_url(url: str) -> str:
    """Extract spreadsheet ID and convert to CSV export link."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError("Invalid Google Sheets URL. Verify sharing link format.")
    spreadsheet_id = match.group(1)
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"

async def fetch_google_sheet(url: str, timeout: float = 10.0) -> bytes:
    """
    Fetch a publicly shared Google Sheet as CSV bytes.
    - Normalizes the URL.
    - Validates public access (checks HTTP 200 and avoids authentication redirects).
    - Uses configured timeout.
    """
    export_url = normalize_google_sheets_url(url)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(export_url, follow_redirects=True, timeout=timeout)
            
            if "ServiceLogin" in str(response.url) or "accounts.google.com" in str(response.url):
                raise ValueError("Google Sheet is private. Please update share settings to 'Anyone with the link can view'.")
                
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch sheet (HTTP {response.status_code})")
                
            return response.content
    except httpx.TimeoutException:
        raise ValueError("Request to Google Sheets timed out")
    except httpx.RequestError as e:
        raise ValueError(f"Failed to connect to Google Sheets: {str(e)}")
