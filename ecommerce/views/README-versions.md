# Ecommerce API Versions

The ecommerce API is versioned differently than other APIs in other OL applications.

The **`legacy`** version is the original version of the ecommerce API, written to work with the MITx Online frontend specifically, and is not exposed via the OpenAPI spec. Its structure is ill-suited for drf-spectactular.

The **`v0`** version is a cross-ported version of the APIs that were in Unified Ecommerce. These are functionally very similar to the `legacy` ones, but they are refactored in a manner that allows them to be exposed via an OpenAPI spec. It seemed like a better idea to pull UE's API set into MITx Online (more or less) as-is, rather than refactor the extant API views to fix them for spec generation.

**New versions** should build off of a tree starting from the `v0` version.
