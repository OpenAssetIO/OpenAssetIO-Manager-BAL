Release Notes
=============

v1.0.0-alpha.4
--------------

### New features

- Added support for `getRelatedReferences` queries against a BAL
  library. See `schema.json` for library syntax, there is an additional
  example in the function's [test library](./tests/resources/library_business_logic_suite_related_references.json).
  [#17](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/17)

### Improvements

- Improved error messaging for missing entities and malformed entity
  references - it now contains the relevant string to aid debugging.

- Bumped OpenAssetIO version to `v1.0.0a8`.


v1.0.0-alpha.3
--------------

### Breaking changes

- Management policy queries will no longer fall back to a hardcoded
  default if no policy was found in the library, and will raise an
  exception instead. If a `managementPolicy` is defined in the JSON
  library, then the JSON schema requires both `read.default` and
  `write.default` policies to be defined.
  [#6](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/6)


v1.0.0-alpha.2
--------------

### Breaking changes

- Renamed the top-level python package to `openassetio_manager_bal`.
  [#9](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/9)

### New features

- BAL now exposes an `openassetio.manager_plugin` entry point, and can
  be installed via `python -m pip` or similar. This allows it to be used
  with OpenAssetIO without needing to extend `OPENASSETIO_PLUGIN_PATH`.
  [#9](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/9)

### Bug fixes

- Updated the JSON schema for `managementPolicy` to properly disallow
  unsupported properties and to support a `write` policy.


v1.0.0-alpha.1
--------------

Initial alpha release.
