from __future__ import annotations

from app.services.product_catalog_service import ProductCatalogService


class TreatmentCatalogService(ProductCatalogService):
    """Legacy alias wrapping ProductCatalogService to support existing clinic/dental integrations."""
    pass
