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
    # sets on a field of the same name collide and both get a hash suffix
    # (DiscountTypeEnum -> DiscountType3beEnum). A hashed name is neither
    # stable across regenerations nor meaningful, and renaming a component
    # that has already been published breaks generated clients. Name every
    # choice set on a field name that more than one of them uses.
    #
    # Keep this as ONE dict. Two `ENUM_NAME_OVERRIDES` keys in this literal is
    # valid Python that silently discards the first, and it is what a rebase
    # produces when two branches each add their own - no conflict, no error,
    # just the other branch's overrides quietly gone.
    "ENUM_NAME_OVERRIDES": {
        # BulkDiscountSerializer restricts discount_type and redemption_type to
        # the subset bulk generation can produce.
        "DiscountTypeEnum": "ecommerce.constants.DISCOUNT_TYPES",
        "RedemptionTypeEnum": "ecommerce.constants.REDEMPTION_TYPES",
        "BulkGenerationDiscountTypeEnum": (
            "ecommerce.constants.BULK_GENERATION_DISCOUNT_TYPES"
        ),
        "BulkGenerationRedemptionTypeEnum": (
            "ecommerce.constants.BULK_GENERATION_REDEMPTION_TYPES"
        ),
        # `state` is used by ecommerce's Order and by both b2b provisioning
        # models. StateEnum is pinned to the one that was published first.
        "StateEnum": "ecommerce.models.OrderStatus",
        "OnboardingStateEnum": "b2b.constants.ONBOARDING_STATE_CHOICES",
        "IdentityProviderLifecycleStateEnum": "b2b.constants.IDP_LIFECYCLE_CHOICES",
        "IdentityProviderProtocolEnum": "b2b.constants.IDP_PROTOCOL_CHOICES",
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
