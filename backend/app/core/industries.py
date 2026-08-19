from enum import Enum

class IndustryType(str, Enum):
    HEALTHCARE_DENTAL = "healthcare_dental"
    REAL_ESTATE = "real_estate"
    INSURANCE = "insurance"
    LOAN_RECOVERY = "loan_recovery"
    GENERIC = "generic"

# All available modules in the CRM platform (including Core and Industry-Specific)
ALL_MODULES = {
    # Generic CRM Core Modules
    "dashboard",
    "leads",
    "contacts",
    "companies",
    "customers",
    "activities",
    "tasks",
    "follow_ups",
    "opportunities",
    "pipelines",
    "communications",
    "billing",
    "reports",
    
    # Dental-Specific Industry Modules
    "patients",
    "appointments",
    "treatments",
    "treatment_plans",
    "recall",
    "dentists",
    "clinical_reports",
}

# Industry business templates defining default enabled modules
BUSINESS_TEMPLATES = {
    IndustryType.HEALTHCARE_DENTAL: {
        "dashboard",
        "leads",
        "patients",
        "appointments",
        "treatments",
        "treatment_plans",
        "recall",
        "dentists",
        "clinical_reports",
        "billing",
        "communications",
        "reports",
    },
    IndustryType.REAL_ESTATE: {
        "dashboard",
        "leads",
        "contacts",
        "companies",
        "opportunities",
        "pipelines",
        "activities",
        "tasks",
        "follow_ups",
        "billing",
        "communications",
        "reports",
    },
    IndustryType.INSURANCE: {
        "dashboard",
        "leads",
        "contacts",
        "companies",
        "opportunities",
        "pipelines",
        "activities",
        "tasks",
        "follow_ups",
        "billing",
        "communications",
        "reports",
    },
    IndustryType.LOAN_RECOVERY: {
        "dashboard",
        "leads",
        "contacts",
        "companies",
        "activities",
        "tasks",
        "follow_ups",
        "billing",
        "communications",
        "reports",
    },
    IndustryType.GENERIC: {
        "dashboard",
        "leads",
        "contacts",
        "companies",
        "opportunities",
        "pipelines",
        "activities",
        "tasks",
        "follow_ups",
        "billing",
        "communications",
        "reports",
    },
}
