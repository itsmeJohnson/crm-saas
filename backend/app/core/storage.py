import os
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Tuple
from app.core.config import settings

logger = logging.getLogger("storage")

# Signature-based Magic Bytes Map
SIGNATURES = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "gif": b"GIF8",
    "pdf": b"%PDF-",
    "xlsx": b"PK\x03\x04",
    "xls": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
}

def is_svg(content: bytes) -> bool:
    """Check if the content is valid SVG (XML containing <svg)."""
    try:
        snippet = content[:2048].decode("utf-8", errors="ignore").strip().lower()
        return "<svg" in snippet
    except Exception:
        return False

def is_csv(content: bytes) -> bool:
    """Check if the content is valid plain-text/CSV."""
    try:
        content[:2048].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False

def validate_and_sanitize_file(
    content: bytes, 
    filename: str, 
    allowed_extensions: set[str], 
    max_size: int = 2 * 1024 * 1024
) -> Tuple[str, str]:
    """
    Validates file size, extension, and checks magic bytes signatures.
    Returns: (sanitized_filename, file_extension)
    """
    # 1. Size Validation
    if len(content) > max_size:
        raise ValueError(f"File size exceeds the limit of {max_size / (1024*1024):.1f}MB")

    # 2. Extension Parsing
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if not ext or ext not in allowed_extensions:
        raise ValueError(f"Extension .{ext} is not allowed")

    # 3. Magic Bytes / Signature Check
    sig_matched = False
    
    # SVG special check
    if ext == "svg":
        if is_svg(content):
            sig_matched = True
        else:
            raise ValueError("Invalid file content for SVG format")
            
    # CSV special check
    elif ext == "csv":
        if is_csv(content):
            sig_matched = True
        else:
            raise ValueError("Invalid file content for CSV format")
            
    # WEBP special check
    elif ext == "webp":
        # WEBP magic bytes: 'RIFF' at 0-4, 'WEBP' at 8-12
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            sig_matched = True
        else:
            raise ValueError("Invalid file content for WEBP format")
            
    # Check other formats
    elif ext in SIGNATURES:
        sig = SIGNATURES[ext]
        if content.startswith(sig):
            sig_matched = True
        else:
            raise ValueError(f"Invalid file signature for .{ext} format")
    else:
        # Fallback for extensions not explicitly in SIGNATURES (if any got through allowed list)
        raise ValueError(f"Extension .{ext} signature validation not supported")

    if not sig_matched:
        raise ValueError("File content did not match its declared extension type")

    # 4. Generate Random Sanitized Filename
    sanitized_filename = f"{uuid.uuid4().hex}.{ext}"
    return sanitized_filename, ext


class StorageProvider(ABC):
    @abstractmethod
    async def upload_file(self, content: bytes, filename: str) -> str:
        """Uploads file content and returns dynamic public url."""
        pass

    @abstractmethod
    async def delete_file(self, file_url: str) -> None:
        """Deletes file corresponding to public url."""
        pass


class LocalStorageProvider(StorageProvider):
    def __init__(self):
        self.upload_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "uploads", 
            "branding"
        )
        os.makedirs(self.upload_dir, exist_ok=True)

    async def upload_file(self, content: bytes, filename: str) -> str:
        filepath = os.path.join(self.upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        return f"/api/v1/uploads/branding/{filename}"

    async def delete_file(self, file_url: str) -> None:
        if not file_url:
            return
        filename = file_url.split("/")[-1]
        filepath = os.path.join(self.upload_dir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                logger.error(f"Failed to delete local file {filepath}: {e}")


class DOSpacesStorageProvider(StorageProvider):
    def __init__(self):
        # We dynamically load boto3 so it is not a hard import error if package is missing
        try:
            import boto3
            self.session = boto3.session.Session()
            self.client = self.session.client(
                's3',
                region_name='nyc3', # Spaces are NYC3 by default or customized
                endpoint_url=settings.SPACES_ENDPOINT,
                aws_access_key_id=settings.SPACES_KEY,
                aws_secret_access_key=settings.SPACES_SECRET
            )
        except ImportError:
            logger.critical("boto3 is required for DOSpacesStorageProvider but not installed.")
            raise RuntimeError("boto3 not installed")

    async def upload_file(self, content: bytes, filename: str) -> str:
        # Run synchronous boto3 upload in executor to keep it async
        import asyncio
        loop = asyncio.get_event_loop()
        
        def _upload():
            self.client.put_object(
                Bucket=settings.SPACES_BUCKET,
                Key=filename,
                Body=content,
                ACL='public-read',
                ContentType=self._get_content_type(filename)
            )
            # URL resolution: either CDN endpoint or standard Spaces URL
            # e.g., https://{bucket}.{endpoint_domain}/{key}
            endpoint_stripped = settings.SPACES_ENDPOINT.replace("https://", "").replace("http://", "")
            return f"https://{settings.SPACES_BUCKET}.{endpoint_stripped}/{filename}"

        return await loop.run_in_executor(None, _upload)

    async def delete_file(self, file_url: str) -> None:
        if not file_url:
            return
        filename = file_url.split("/")[-1]
        import asyncio
        loop = asyncio.get_event_loop()
        
        def _delete():
            self.client.delete_object(
                Bucket=settings.SPACES_BUCKET,
                Key=filename
            )

        try:
            await loop.run_in_executor(None, _delete)
        except Exception as e:
            logger.error(f"Failed to delete remote Spaces file {filename}: {e}")

    def _get_content_type(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "svg": "image/svg+xml",
            "webp": "image/webp",
            "pdf": "application/pdf"
        }
        return types.get(ext, "application/octet-stream")


def get_storage_provider() -> StorageProvider:
    """Returns DOSpacesStorageProvider if config parameters exist, else LocalStorageProvider."""
    if settings.SPACES_KEY and settings.SPACES_SECRET and settings.SPACES_ENDPOINT and settings.SPACES_BUCKET:
        try:
            return DOSpacesStorageProvider()
        except Exception as e:
            logger.error(f"Failed to initialize DigitalOcean Spaces provider, fallback to LocalStorage: {e}")
            return LocalStorageProvider()
    return LocalStorageProvider()
