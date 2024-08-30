Release Notes
=============

v1.0.0-beta.1.0
---------------

### Breaking changes

- Removed support for VFX Reference Platform CY22 or lower. This means
  Python 3.7 and 3.9 builds are no longer tested or published.
  [OpenAssetIO#1351](https://github.com/OpenAssetIO/OpenAssetIO/issues/1351)

- Minimum OpenAssetIO version increased to v1.0.0-beta.2.2 to make use
  of new API features.
  [#84](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/84)

- Minimum OpenAssetIO-MediaCreation version increased to v1.0.0-alpha.9
  for compatibility with the latest OpenAssetIO. See
  [OpenAssetIO#1311](https://github.com/OpenAssetIO/OpenAssetIO/issues/1311).
  [#90](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/90)

### New features

- Added support for configuring the result of `hasCapability(...)`
  queries. This allows hosts to test their logic when dealing with
  managers that have limited capability.
  [#84](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/84)

- Added support for `OPENASSETIO_BAL_IDENTIFIER` environment variable,
  for overriding the identifier advertised by the BAL plugin/manager.
  [#116](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/pull/116)

- Added support for the `defaultEntityReference` core API method,
  configured using a new JSON field in the database `"defaultEntities"`,
  which maps access mode and trait set to an entity name.
  [#53](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/53)

v1.0.0-alpha.16
---------------

### Bug fixes

- Fixed normalisation of `file://` URLs from the JSON database such that
  they are no longer percent decoded before being passed on to the host.
  [#109](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/109)

v1.0.0-alpha.15
---------------

### Breaking changes

- Minimum OpenAssetIO version increased to v1.0.0-beta.2.1 to make use
  of new API features.
  [#90](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/90)

- Renamed the key for configuring per trait set `managementPolicy`
  responses in the JSON database from `"exceptions"` to
  `"overrideByTraitSet"`.
  [#90](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/90)

### New features

- Added validation during publishing against `managementPolicy` and the
  `kWrite` entity trait set.
  [#90](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/90)

- Added `"overrideByAccess"` option in the JSON DB entity entries,
  allowing per access mode overrides of returned data, with `null`
  signalling non-existence and empty dict `{}` signalling
  inaccessibility.
  [#90](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/90)

- Add new `bal_library_dir_url` substitution variable, allowing library
  directory to be used in places where OpenAssetIO requires a valid
  url.
  [#86](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/86)

### Bug fixes

- Fixed `resolve` to no longer imbue entity traits that have no
  property values.

- Fixed to trigger a `kEntityResolutionError` result, rather than
  `IndexError` exception, when querying an empty `"versions"` list in
  the JSON database.
  [#90](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/90)

v1.0.0-alpha.14
---------------

### Breaking changes

- Reverted `openassetio-mediacreation` to an explicit package
  dependency, now that
  https://github.com/OpenAssetIO/OpenAssetIO/issues/1088 is complete,
  and conflicting installation requirements will be handled correctly.
  [#72](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/72)

- Minimum OpenAssetIO version increased to v1.0.0-beta.2.0 due to
  breaking API changes.
  [#89](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/89)

### New features

- Added support for the `entityTraits` core API method.
  [#89](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/89)

- Added support for the `kRequired` and `kManagerDriven` access modes in
  `managementPolicy` queries. Added support for access modes other than
  `kRead` in `resolve` queries (i.e. `kManagerDriven`).
  [#98](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/98)

v1.0.0-alpha.13
---------------

### New features

- Added support for querying a stable equivalent reference using the
  OpenAssetIO-MediaCreation `StableReferenceRelationshipSpecification`
  with `getWithRelationship`.
  [#83](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/pull/83)

v1.0.0-alpha.12
---------------

### Breaking changes

- Minimum OpenAssetIO version increased to v1.0.0-beta.1.0 due to
  breaking API changes.
  [#1119](https://github.com/OpenAssetIO/OpenAssetIO/issues/1119)
  [#1125](https://github.com/OpenAssetIO/OpenAssetIO/issues/1125)
  [#1127](https://github.com/OpenAssetIO/OpenAssetIO/issues/1127)

- Added `openassetio` as a package dependency to aid debugging
  versions conflicts.

v1.0.0-alpha.11
---------------

### Bug fixes

- Made `openassetio-mediacreation` a soft dependency to avoid
  conflicting installation requirements.

v1.0.0-alpha.10
---------------

### Breaking changes

- Refactored entity reference handling, resulting in a change to
  exception message formatting for malformed entity references.

- Migrated `entityExists` to the batch-first callback based signature.

- Entity references returned from `register` will now contain a
  version specifier in the `v=<version>` query parameter.
  [#49](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/pull/49)

- Added a runtime dependency on the `openassetio-mediacreation` package.

- Added validation to API methods to error on unsupported access modes.
  [#57](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/57)

- Minimum OpenAssetIO version increased to v1.0.0-alpha.14 due to
  breaking API changes.
  [#1054](https://github.com/OpenAssetIO/OpenAssetIO/issues/1054)

### New features

- The entity reference scheme consumed by BAL can be adjusted from the
  default of `bal` using the `entity_reference_url_scheme` setting.
  This must be set to a simple alphanumeric string.

- Added support for retrieving specific versions using the `v=<version>`
  query parameter in a BAL entity reference. When publishing,
  `preflight` will remove any explicit version specifier (as it will
  always produce a new version), and `register` will return an entity
  reference with the version specifier for the newly created version.
  [#49](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/pull/49)

- Added support for resolving the OpenAssetIO-MediaCreation
  `VersionTrait`.
  [#49](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/pull/49)

- Added support for querying entity versions using the
  OpenAssetIO-MediaCreation `EntityVersionsRelationshipSpecification` and
  `StableEntityVersionsRelationshipSpecification` with
  `getWithRelationship`. If the `specifiedVersion` property of the
  `VersionTrait` is set, then a reference for that version will be
  returned.
  [#49](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/pull/49)

### Bug fixes

- Added missing fixtures for the `openassetio.test.manager` API
  compliance suite test harness.
  [#61](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/pull/61)

v1.0.0-alpha.9
--------------

### Breaking changes

- Minimum OpenAssetIO version increased to `v1.0.0-alpha.13` due to API
  changes.

- Refactored error handling. `BatchElementError` messages have been
  reformatted when a referenced entity is missing from the library.

### New Features

- Added support for `getWithRelationship[s]Paged` paged relationship
  query API.
  [#46](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL/issues/46)

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
  library. See `schema.json` for library syntax, there an example in the
  function's [test
  library](./tests/resources/library_apiComplianceSuite.json).
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
