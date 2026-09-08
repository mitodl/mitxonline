"""
Django settings specific to DRF Spectacular
"""

open_spectacular_settings = {
    "TITLE": "MITx Online API",
    "DESCRIPTION": "MIT public API",
    "VERSION": "0.0.1",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_URLCONF": "main.urls",
    "ENUM_GENERATE_CHOICE_DESCRIPTION": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "AUTHENTICATION_WHITELIST": [],
    "SCHEMA_PATH_PREFIX": "/api/v[0-9]",
    # drf-spectacular names an enum component after its field, so two choice
    # sets on a field called discount_type collide and both get a hash suffix.
    # BulkDiscountSerializer restricts discount_type and redemption_type to the
    # subset bulk generation can produce, so name every set on those two fields.
    "ENUM_NAME_OVERRIDES": {
        "DiscountTypeEnum": "ecommerce.constants.DISCOUNT_TYPES",
        "RedemptionTypeEnum": "ecommerce.constants.REDEMPTION_TYPES",
        "BulkGenerationDiscountTypeEnum": (
            "ecommerce.constants.BULK_GENERATION_DISCOUNT_TYPES"
        ),
        "BulkGenerationRedemptionTypeEnum": (
            "ecommerce.constants.BULK_GENERATION_REDEMPTION_TYPES"
        ),
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "openapi.hooks.postprocess_x_enum_descriptions",
    ],
    "PREPROCESSING_HOOKS": [
        "openapi.hooks.exclude_paths_hook",
        "openapi.hooks.insert_wagtail_pages_schema",
    ],
}
