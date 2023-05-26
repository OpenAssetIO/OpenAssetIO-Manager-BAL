Release Notes
=============

v1.0.0-alpha.x
--------------

### Breaking Changes

- Refactored error handling. `BatchElementError` messages have been
  reformatted when a referenced entity is missing from the library.

v1.0.0-alpha.8
--------------

### New Features

- Added capability to artificially delay `resolve`, `preflight`,
  `entityExists`, `register` and `getRelatedReferences` in order to
  better simulate real-world workflows and better test scalability. New
  setting `simulated_query_latency_ms` added, defaulting to 10ms.
  [#38](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/38)

v1.0.0-alpha.7
--------------

### Improvements

- Moved `openassetio` dependency out of python project
  (`pyproject.toml`) and instead have it as a `requirements.txt`
  dependency. OpenAssetIO should be provided by the environment, and BAL
  enforcing this as part of its install led to inflexibility.
  [#31](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/31)

v1.0.0-alpha.6
--------------

### Bug fixes

- The `$BAL_LIBRARY_PATH` environment variable is now correctly
  considered when the `library_path` setting is not set/empty.
  [#26](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/26)

v1.0.0-alpha.5
--------------

### New features

- Variables are now expanded in any string properties of an entity's
  traits. Expansion occurs during resolve to allow for variation in the
  environment between calls. Note: Only the `$var` and `${var}` syntax
  is supported. You can escape a literal `$` using `$$`. In addition to
  the environment, a library can define arbtirary variables under the
  top level `variables` key. BAL also provides several implicit
  variables of its own:
  - `bal_library_path` The absolute path to the current library.
  - `bal_library_dir` The absolute path to the directory containing the
     current library.
  [#22](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/22)

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
