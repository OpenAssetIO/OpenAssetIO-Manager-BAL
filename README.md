# The Basic Asset Library (BAL) example manager

The BasicAssetLibrary provides a basic "librarian" asset management
system.

It serves to provide a minimum level of functionality to allow simple,
repeatable demonstrations and end-to-end tests to be realized with as
little supporting infrastructure as possible.

It is not intended to be any kind of comprehensive example of the
breadth of functionality exposed though the OpenAssetIO API.
See the SampleAssetManager for a more concrete example of canonical
manager behavior.

> Note: This code is a sketch to facilitate testing and sample
> workflows. It should never be considered in any way a "good example
> of how to write an asset management system". Consequently, it omits
> a plethora of "good engineering practice".

## Features

- Resolves references with the `bal:///` prefix to data from a
  pre-configured library of assets stored in a `.json` file.

- Environment variables are expanded in string-type trait property
  values (using the `$var` or `${var}` syntax, escape `$` using `$$`). A
  library can also define arbitrary variables of its own under the
  top-level `variables` key. In addition, BAL provides the built-in
  `$bal_library_path` and `$bal_library_dir` variables, which can be
  used to anchor to the current library location.

- The library file to be used is controlled by the `library_path`
  setting, and this should point to a library file with valid content.

- If no `library_path` has been specified, the `BAL_LIBRARY_PATH` env
  var will be checked to see if it points to a valid library file.

- Persists newly registered data in-memory (the original library JSON is
  not updated).

## Installation

To use the plugin in an OpenAssetIO host, install via `pip`, or set (or append) the
`OPENASSETIO_PLUGIN_PATH` env var to include the `plugin` directory in
a checkout of the [source repository](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL).

The plugin provides a manager with the identifier
`org.openassetio.examples.manager.bal`.

```bash
python -m pip install openassetio-manager-bal
```

## Library file format

A [JSON Schema](https://json-schema.org) is provided
[here](https://raw.githubusercontent.com/OpenAssetIO/OpenAssetIO-Manager-BAL/main/schema.json)
that validates a BAL library file.

## Testing

The test fixtures take care of providing a suitable host environment and
configuring the OpenAssetIO plugin search paths for you. Assuming your
working directory is set to a checkout of the
[source repository](https://github.com/OpenAssetIO/OpenAssetIO-Manager-BAL):

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r tests/requirements.txt
python -m pip install .
python -m pytest ./tests
```
