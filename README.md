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

- The library file to be used is controlled by the `library_path`
  setting, and this should point to a library file with valid content.

- If no `library_path` has been specified, the `BAL_LIBRARY_PATH` env
  var will be checked to see if it points to a valid library file.

- Persists newly registered data in-memory (the original library JSON is
  not updated).

## Installation

To use the plugin in an OpenAssetIO host, set (or append) the
`OPENASSETIO_PLUGIN_PATH` env var to include the `python` directory in
this checkout.

The plugin provides a manager with the identifier
`org.openassetio.examples.manager.bal`.

The plugin requires `openassetio` to be available to python at
runtime. This is normally provided by the host tool or application (see
the [project documentation](https://github.com/OpenAssetIO/OpenAssetIO#getting-started)
for more information if you need to install yourself).

## Library file format

A [JSON Schema](https://json-schema.org) is provided [here](schema.json)
that validates a BAL library file.

## Testing

The test fixtures take care of configuring the OpenAssetIO plugin search
paths for you. Assuming your working directory is set to the root of
this checkout:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r tests/requirements.txt
pytest
```
