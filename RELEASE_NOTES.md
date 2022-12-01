Release Notes
=============

v1.0.0-alpha.x
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
