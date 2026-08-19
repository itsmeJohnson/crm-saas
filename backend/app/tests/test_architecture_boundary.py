"""Phase 3.1 architecture-guard tests.

These lock the CRM-Core ↔ Dental boundary so it cannot silently regress:

  1. No Core table carries a Dental-semantic foreign key / column.
  2. The generic domain layer never imports the Dental-named compatibility
     layer (import direction must stay Industry -> Core, never Core -> Dental).
  3. The industry registry keeps Core and Dental module keys disjoint, and the
     non-dental business templates never enable Dental modules.

They are pure static/metadata checks — no database or network required.
"""
import re
from pathlib import Path

import pytest

import app.models  # noqa: F401 — ensures every model is registered on Base.metadata
from app.models.base import Base
from app.core.industries import ALL_MODULES, BUSINESS_TEMPLATES, IndustryType

# Dental-semantic column/relationship fragments that must never appear on a Core table.
DENTAL_COLUMN_PATTERNS = re.compile(
    r"patient|dentist|treatment|appointment|tooth|clinical|recall|procedure",
    re.IGNORECASE,
)

# Tables that make up the industry-neutral CRM Core.
CORE_TABLES = {
    "leads",
    "contacts",
    "companies",
    "customer_orders",
    "customer_invoices",
    "customer_payments",
    "activities",
    "tasks",
    "notes",
    "communication_templates",
    "pipelines",
    "pipeline_stages",
    "product_catalog_items",
}

# Dental module keys as declared in core/industries.py.
DENTAL_MODULE_KEYS = {
    "patients",
    "appointments",
    "treatments",
    "treatment_plans",
    "recall",
    "dentists",
    "clinical_reports",
}

CORE_MODULE_KEYS = {
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
}

BACKEND_APP = Path(__file__).resolve().parents[1]  # backend/app


def test_core_tables_have_no_dental_columns():
    """No Core table may carry a Dental-semantic column (patient_id, dentist_id,
    treatment_id, appointment_id, tooth/clinical/recall/procedure). Dental data
    must live in the generic ``custom_fields`` JSON, not in Core schema."""
    offenders = []
    for table_name in CORE_TABLES:
        table = Base.metadata.tables.get(table_name)
        assert table is not None, f"Expected Core table '{table_name}' to be registered"
        for column in table.columns:
            if DENTAL_COLUMN_PATTERNS.search(column.name):
                offenders.append(f"{table_name}.{column.name}")
    assert not offenders, (
        "Core tables must not carry Dental-semantic columns; found: " + ", ".join(offenders)
    )


def test_generic_domain_layer_does_not_import_dental_compat():
    """The generic product-catalog domain must not import the Dental-named
    treatment-catalog compat layer. Direction is treatment_catalog -> product_catalog,
    never the reverse."""
    generic_files = [
        BACKEND_APP / "services" / "product_catalog_service.py",
        BACKEND_APP / "schemas" / "product_catalog.py",
        BACKEND_APP / "models" / "product_catalog.py",
        BACKEND_APP / "api" / "v1" / "product_catalog.py",
    ]
    offenders = []
    for f in generic_files:
        if not f.exists():
            continue
        text = f.read_text()
        if "treatment_catalog" in text:
            offenders.append(f.relative_to(BACKEND_APP).as_posix())
    assert not offenders, (
        "Generic product-catalog layer must not depend on the Dental treatment_catalog "
        "compat layer; offenders: " + ", ".join(offenders)
    )


def test_custom_fields_engine_imports_no_industry_modules():
    """Phase 4.1: the Custom Fields Engine belongs to CRM Core. None of its
    modules may import a Dental/industry module (import direction Industry→Core)."""
    engine_files = [
        BACKEND_APP / "core" / "custom_field_types.py",
        BACKEND_APP / "core" / "reserved_fields.py",
        BACKEND_APP / "core" / "record_query.py",
        BACKEND_APP / "services" / "custom_field_service.py",
        BACKEND_APP / "services" / "metadata_validation_engine.py",
        BACKEND_APP / "services" / "custom_object_service.py",
        BACKEND_APP / "services" / "custom_object_record_service.py",
        BACKEND_APP / "models" / "custom_field_definition.py",
        BACKEND_APP / "models" / "custom_object.py",
        BACKEND_APP / "schemas" / "custom_field.py",
        BACKEND_APP / "schemas" / "custom_object.py",
        BACKEND_APP / "api" / "v1" / "custom_objects.py",
    ]
    industry_import = re.compile(
        r"import.*(treatment_catalog|dental|patient|appointment|dentist|clinical|"
        r"real_estate|property|insurance|policy|loan_recovery)",
        re.IGNORECASE,
    )
    offenders = []
    for f in engine_files:
        assert f.exists(), f"Expected Custom Fields Engine file to exist: {f}"
        for i, line in enumerate(f.read_text().splitlines(), 1):
            stripped = line.strip()
            if (stripped.startswith("import ") or stripped.startswith("from ")) and industry_import.search(stripped):
                offenders.append(f"{f.name}:{i}: {stripped}")
    assert not offenders, "Custom Fields Engine imports industry modules: " + "; ".join(offenders)


def test_custom_field_supported_entities_are_core_only():
    """The engine's supported entity types must be generic Core entities only —
    never a Dental/industry entity like patient/appointment."""
    from app.core.reserved_fields import SUPPORTED_ENTITY_TYPES
    assert SUPPORTED_ENTITY_TYPES == {"lead", "contact"}
    forbidden = {"patient", "appointment", "treatment", "property", "policy", "loan", "case"}
    assert SUPPORTED_ENTITY_TYPES.isdisjoint(forbidden)


def test_core_module_keys_and_dental_keys_are_disjoint():
    assert CORE_MODULE_KEYS.isdisjoint(DENTAL_MODULE_KEYS)
    # Every declared key must be known to the platform registry.
    assert CORE_MODULE_KEYS.issubset(ALL_MODULES)
    assert DENTAL_MODULE_KEYS.issubset(ALL_MODULES)


@pytest.mark.parametrize(
    "industry",
    [IndustryType.REAL_ESTATE, IndustryType.INSURANCE, IndustryType.LOAN_RECOVERY, IndustryType.GENERIC],
)
def test_non_dental_templates_enable_no_dental_modules(industry):
    """A non-dental business template must never turn on a Dental module key."""
    enabled = BUSINESS_TEMPLATES[industry]
    leaked = enabled & DENTAL_MODULE_KEYS
    assert not leaked, f"{industry.value} template leaks Dental modules: {leaked}"


def test_dental_template_enables_dental_modules():
    """Sanity: the dental template DOES enable dental modules (guards against the
    guard itself going vacuously true)."""
    enabled = BUSINESS_TEMPLATES[IndustryType.HEALTHCARE_DENTAL]
    assert {"patients", "treatments"}.issubset(enabled)
