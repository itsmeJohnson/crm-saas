import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization
from app.core.industries import BUSINESS_TEMPLATES, IndustryType

class TenantConfigurationResolver:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_config(self, organization_id: uuid.UUID) -> dict:
        """Resolves template modules merged with per-tenant enabled_modules overrides."""
        res = await self.db.execute(
            select(Organization).filter(Organization.id == organization_id)
        )
        org = res.scalars().first()
        if not org:
            # Fallback default configuration
            return {
                "industry": IndustryType.HEALTHCARE_DENTAL.value,
                "template": IndustryType.HEALTHCARE_DENTAL.value,
                "enabled_modules": list(BUSINESS_TEMPLATES[IndustryType.HEALTHCARE_DENTAL]),
            }

        industry_val = org.industry or IndustryType.HEALTHCARE_DENTAL.value
        template_val = org.business_template or IndustryType.HEALTHCARE_DENTAL.value

        try:
            industry_enum = IndustryType(industry_val)
        except ValueError:
            industry_enum = IndustryType.HEALTHCARE_DENTAL

        try:
            template_enum = IndustryType(template_val)
        except ValueError:
            template_enum = IndustryType.HEALTHCARE_DENTAL

        default_modules = BUSINESS_TEMPLATES.get(template_enum, BUSINESS_TEMPLATES[IndustryType.HEALTHCARE_DENTAL])

        if org.enabled_modules is not None:
            if isinstance(org.enabled_modules, list):
                enabled_modules = list(set(org.enabled_modules))
            else:
                enabled_modules = list(default_modules)
        else:
            enabled_modules = list(default_modules)

        return {
            "industry": industry_enum.value,
            "template": template_enum.value,
            "enabled_modules": enabled_modules,
        }
