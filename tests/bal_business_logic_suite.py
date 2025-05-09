#
#   Copyright 2013-2021 The Foundry Visionmongers Ltd
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
"""
A manager test harness test case suite that validates that the
BasicAssetLibrary manager behaves with the correct business logic.
"""

# pylint: disable=invalid-name, missing-function-docstring, missing-class-docstring,
# pylint: disable=too-few-public-methods,too-many-lines

import json
import operator
import os
import pathlib

from unittest import mock

from openassetio import constants
from openassetio.hostApi import Manager
from openassetio.managerApi import ManagerInterface
from openassetio.access import (
    PolicyAccess,
    PublishingAccess,
    DefaultEntityAccess,
    RelationsAccess,
    ResolveAccess,
    EntityTraitsAccess,
)
from openassetio.errors import (
    BatchElementError,
    BatchElementException,
    ConfigurationException,
    NotImplementedException,
)
from openassetio.test.manager.harness import FixtureAugmentedTestCase
from openassetio.trait import TraitsData
from openassetio.utils import FileUrlPathConverter

import openassetio_mediacreation
from openassetio_mediacreation.traits.lifecycle import VersionTrait
from openassetio_mediacreation.specifications.lifecycle import (
    EntityVersionsRelationshipSpecification,
    StableEntityVersionsRelationshipSpecification,
    StableReferenceRelationshipSpecification,
)

# pylint can't load this module simply, we just want to import it to
# test the asymmetric manager/managerInterface capabilities enum.
# pylint: disable=E0401
from openassetio_manager_bal.BasicAssetLibraryInterface import BasicAssetLibraryInterface

__all__ = []

LIBRARY_PATH_VARNAME = "BAL_LIBRARY_PATH"


class LibraryOverrideTestCase(FixtureAugmentedTestCase):
    """
    Utility base class to load a custom BAL library for the duration of
    the tests in a subclass.

    Assumes a `_library` class attribute that gives the name of the JSON
    file to load from the `resources` directory.
    """

    _library = None

    def setUp(self):
        self.__old_settings = self._manager.settings()
        new_settings = self.__old_settings.copy()
        new_settings["library_path"] = os.path.join(
            os.path.dirname(__file__),
            "resources",
            self._library,
        )
        # library_json takes precedence, so remove library_json to
        # ensure library_path is used.
        del new_settings["library_json"]

        self.addCleanup(self.cleanUp)
        self._manager.initialize(new_settings)

    def cleanUp(self):
        self._manager.initialize(self.__old_settings)


class GetWithRelationshipTestCase(FixtureAugmentedTestCase):
    """
    A helper class to share common utiities that relate to tests of the
    relatiionship query methods.
    """

    def assertExpectedRefs(self, ref, relationship, expected_refs, access=RelationsAccess.kRead):
        """
        Fetches all relations and asserts that they match expectations.
        """
        result_refs = []

        self._manager.getWithRelationship(
            [ref],
            relationship,
            1000,
            access,
            self.createTestContext(),
            lambda idx, pager: result_refs.extend(pager.get()),
            lambda _, err: self.fail(f"Failed to query relationships: {err.code} {err.message}"),
        )

        self.assertEqual(
            [r.toString() for r in result_refs], [r.toString() for r in expected_refs]
        )

        result_refs = []

        self._manager.getWithRelationships(
            ref,
            [relationship],
            1000,
            access,
            self.createTestContext(),
            lambda idx, pager: result_refs.extend(pager.get()),
            lambda _, err: self.fail(f"Failed to query relationships: {err.code} {err.message}"),
        )

        self.assertEqual(
            [r.toString() for r in result_refs], [r.toString() for r in expected_refs]
        )


class Test_initialize_library_path(FixtureAugmentedTestCase):
    shareManager = False

    alt_lib_path = os.path.join(os.path.dirname(__file__), "resources", "library_empty.json")

    @mock.patch.dict(os.environ)
    def test_when_setting_and_env_not_set_then_ConfigurationException_raised(self):
        if LIBRARY_PATH_VARNAME in os.environ:
            del os.environ[LIBRARY_PATH_VARNAME]
        with self.assertRaises(ConfigurationException):
            self._manager.initialize({})

    @mock.patch.dict(os.environ)
    def test_when_setting_not_set_and_env_set_then_env_used(self):
        os.environ[LIBRARY_PATH_VARNAME] = self.alt_lib_path
        self._manager.initialize({})
        self.assertEqual(self._manager.settings()["library_path"], self.alt_lib_path)

    @mock.patch.dict(os.environ)
    def test_when_setting_set_and_env_not_set_then_setting_used(self):
        if LIBRARY_PATH_VARNAME in os.environ:
            del os.environ[LIBRARY_PATH_VARNAME]
        self._manager.initialize({"library_path": self.alt_lib_path})
        self.assertEqual(self._manager.settings()["library_path"], self.alt_lib_path)

    @mock.patch.dict(os.environ)
    def test_when_setting_and_env_set_then_setting_used(self):
        os.environ[LIBRARY_PATH_VARNAME] = "I do not exist"
        self._manager.initialize({"library_path": self.alt_lib_path})
        self.assertEqual(self._manager.settings()["library_path"], self.alt_lib_path)

    @mock.patch.dict(os.environ)
    def test_when_setting_and_env_blank_then_ConfigurationException_raised(self):
        os.environ[LIBRARY_PATH_VARNAME] = ""
        with self.assertRaises(ConfigurationException):
            self._manager.initialize({"library_path": ""})

    @mock.patch.dict(os.environ)
    def test_when_setting_blank_and_env_set_then_env_used(self):
        os.environ[LIBRARY_PATH_VARNAME] = self.alt_lib_path
        self._manager.initialize({"library_path": ""})
        self.assertEqual(self._manager.settings()["library_path"], self.alt_lib_path)


class Test_initialize_entity_reference_scheme(FixtureAugmentedTestCase):
    shareManager = False

    def test_when_not_set_then_default_is_bal(self):
        self.initialize_and_assert_scheme()

    def test_when_set_with_valid_scheme_then_used(self):
        for scheme in ("mal", "some-very-long-string", "bal2"):
            with self.subTest(scheme=scheme):
                self.initialize_and_assert_scheme(scheme)

    def test_when_set_with_invalid_sceheme_then_exception_raised(self):
        for scheme in ("", "c://b", "no_us", "sadly no 🦆", "or spaces", 234, False):
            with self.subTest(scheme=scheme):
                with self.assertRaises(ValueError):
                    self.initialize_and_assert_scheme(scheme)

    def initialize_and_assert_scheme(self, scheme=None):
        settings = {
            "library_path": os.path.join(resources_path(), "library_apiComplianceSuite.json")
        }
        if scheme is not None:
            settings["entity_reference_url_scheme"] = scheme
        else:
            scheme = "bal"

        prefix = f"{scheme}:///"

        self._manager.initialize(settings)

        # Assert prefix used for short-circuit optimization
        self.assertEqual(
            self._manager.info()[constants.kInfoKey_EntityReferencesMatchPrefix], prefix
        )

        context = self.createTestContext()

        # Assert prefix used for queries
        ref = self._manager.createEntityReference(f"{prefix}anAsset⭐︎")

        self._manager.entityExists(
            [ref],
            context,
            lambda idx, exists: self.assertTrue(exists),
            lambda idx, error: self.fail(
                f"Failed to check existence of reference: {error.message}"
            ),
        )

        # Assert prefix used to generate new references
        published_refs = [None]
        self._manager.register(
            [self._manager.createEntityReference(f"{prefix}a_new_entity_for_scheme_{scheme}")],
            [TraitsData({"someTrait"})],
            PublishingAccess.kWrite,
            context,
            lambda idx, published_ref: operator.setitem(published_refs, idx, published_ref),
            lambda _, err: self.fail(f"Failed to create new entity: {err.code} {err.message}"),
        )
        self.assertTrue(str(published_refs[0]).startswith(prefix))


class Test_initialize_library_as_json_string(LibraryOverrideTestCase):
    # Override library just to ensure the cleanup step gets added,
    # restoring the library back to its original state. See base class.
    _library = "library_apiComplianceSuite.json"

    def test_when_library_loaded_from_file_then_library_setting_contains_file_contents(self):
        settings = self._manager.settings()
        library_path = pathlib.Path(settings["library_path"])
        expected_library = json.loads(library_path.read_text(encoding="utf-8"))
        actual_library = json.loads(settings["library_json"])

        # For simplicity, strip dynamically calculated values.
        del actual_library["variables"]
        self.assertDictEqual(expected_library, actual_library)

    def test_when_library_json_updated_then_settings_updated(self):
        expected_library = {"managementPolicy": {"read": {"default": {"some.policy": {}}}}}

        self._manager.initialize({"library_json": json.dumps(expected_library)})

        actual_library = json.loads(self._manager.settings()["library_json"])

        self.assertDictEqual(actual_library, expected_library)

    def test_when_library_json_is_invalid_primitive_value_then_raises(self):
        with self.assertRaises(ValueError) as err:
            self._manager.initialize({"library_json": ""})

        self.assertEqual("library_json must be a valid JSON string", str(err.exception))

    def test_when_library_json_is_invalid_object_then_raises(self):
        with self.assertRaises(TypeError) as err:
            self._manager.initialize({"library_json": {"variables": {"a": "b"}}})

        # Error comes from pybind11 trying to coerce dict.
        self.assertIn("incompatible function arguments", str(err.exception))

    def test_when_library_json_provided_and_library_path_blank_then_settings_updated(self):
        # Test to ensure we don't error on a blank library_path if
        # library_json is given

        expected_library = {"managementPolicy": {"read": {"default": {"some.policy": {}}}}}

        self._manager.initialize(
            {"library_json": json.dumps(expected_library), "library_path": ""}
        )

        actual_library = json.loads(self._manager.settings()["library_json"])

        self.assertDictEqual(actual_library, expected_library)

    def test_when_no_library_json_and_library_path_blank_then_raises(self):
        expected_error = "'library_json'/'library_path'/BAL_LIBRARY_PATH not set or is empty"

        with self.assertRaises(ConfigurationException) as exc:
            self._manager.initialize({"library_path": ""})

        self.assertEqual(str(exc.exception), expected_error)

    def test_when_library_provided_as_json_and_as_file_then_json_takes_precedence(self):
        library_path = self._manager.settings()["library_path"]
        self.assertGreater(len(library_path), 0)  # Confidence check.
        expected_library = {"variables": {"a": "b"}}

        self._manager.initialize(
            {"library_json": json.dumps(expected_library), "library_path": library_path}
        )
        actual_library = json.loads(self._manager.settings()["library_json"])

        self.assertDictEqual(expected_library, actual_library)

    def test_when_initialised_with_no_library_json_then_resets_to_library_file(self):
        # Read in initial library file.
        library_path = pathlib.Path(self._manager.settings()["library_path"])
        expected_library = json.loads(library_path.read_text(encoding="utf-8"))
        self.assertGreater(len(expected_library), 0)  # Confidence check.

        # Mutate library (to empty dict).
        self._manager.initialize({"library_json": "{}"})
        self.assertEqual("{}", self._manager.settings()["library_json"])  # Confidence check.

        # Re-`initialize` with an empty settings dict, triggering a
        # reset of the library to use the previous `library_path` file.
        self._manager.initialize({})

        actual_library = json.loads(self._manager.settings()["library_json"])

        # For simplicity, strip dynamically calculated values.
        del actual_library["variables"]
        self.assertDictEqual(expected_library, actual_library)

    def test_when_in_memory_library_is_updated_then_library_json_is_updated(self):
        # Publish a new entity that is not in the initial JSON library.
        # This will mutate BAL's in-memory library.
        self._manager.register(
            self._manager.createEntityReference("bal:///new_entity"),
            TraitsData(),
            PublishingAccess.kWrite,
            self.createTestContext(),
        )

        library = json.loads(self._manager.settings()["library_json"])

        self.assertIn("new_entity", library["entities"])

    def test_when_library_uses_undefined_substitution_variables_then_variables_not_substituted(
        self,
    ):
        # Test illustrating that implicit variables for interpolation
        # are not available when library is given as a JSON string,
        # unlike for library files.

        # setup

        expected_library_json = json.dumps(
            {
                "entities": {
                    "some_entity": {
                        "versions": [
                            {"traits": {"some.trait": {"some_key": "${bal_library_path}"}}}
                        ]
                    }
                }
            }
        )

        # action

        self._manager.initialize({"library_json": expected_library_json})

        # confirm

        traits_data = self._manager.resolve(
            self._manager.createEntityReference("bal:///some_entity"),
            {"some.trait"},
            ResolveAccess.kRead,
            self.createTestContext(),
        )
        self.assertEqual(
            traits_data.getTraitProperty("some.trait", "some_key"), "${bal_library_path}"
        )

    def test_when_library_uses_defined_substitution_variables_then_variables_are_substituted(
        self,
    ):
        # Test illustrating that variables for interpolation must be
        # explicitly provided when library is given as a JSON string.
        # I.e. there are no implicit variables, unlike when the library
        # is given as a JSON file.

        # setup

        expected_library_json = json.dumps(
            {
                "variables": {"bal_library_path": "/some/path"},
                "entities": {
                    "some_entity": {
                        "versions": [
                            {"traits": {"some.trait": {"some_key": "${bal_library_path}"}}}
                        ]
                    }
                },
            }
        )

        # action

        self._manager.initialize({"library_json": expected_library_json})

        # confirm

        traits_data = self._manager.resolve(
            self._manager.createEntityReference("bal:///some_entity"),
            {"some.trait"},
            ResolveAccess.kRead,
            self.createTestContext(),
        )
        self.assertEqual(traits_data.getTraitProperty("some.trait", "some_key"), "/some/path")


class Test_managementPolicy_missing_completely(LibraryOverrideTestCase):
    """
    Tests error case when  BAL library managementPolicy is missing.
    """

    _library = "library_business_logic_suite_blank.json"

    def test_when_read_policy_queried_from_library_with_no_policies_then_raises_exception(
        self,
    ):
        context = self.createTestContext()

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], PolicyAccess.kRead, context)

        self.assertEqual(
            str(ex.exception),
            "BAL library is missing a managementPolicy for 'read'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema.",
        )

    def test_when_write_policy_queried_from_library_with_no_policies_then_raises_exception(
        self,
    ):
        context = self.createTestContext()

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], PolicyAccess.kWrite, context)

        self.assertEqual(
            str(ex.exception),
            "BAL library is missing a managementPolicy for 'write'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema.",
        )


class Test_managementPolicy_missing_default(LibraryOverrideTestCase):
    """
    Tests error case when  BAL library managementPolicy is missing a
    "default" policy.
    """

    _library = "library_business_logic_suite_managementPolicy_missing_default.json"

    def test_when_read_policy_queried_from_library_missing_default_policy_then_raises_exception(
        self,
    ):
        context = self.createTestContext()

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], PolicyAccess.kRead, context)

        self.assertEqual(
            str(ex.exception),
            "BAL library is missing a managementPolicy for 'read'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema.",
        )

    def test_when_write_policy_queried_from_library_missing_default_policy_then_raises_exception(
        self,
    ):
        context = self.createTestContext()

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], PolicyAccess.kWrite, context)

        self.assertEqual(
            str(ex.exception),
            "BAL library is missing a managementPolicy for 'write'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema.",
        )


class Test_managementPolicy_library_specified_behavior(LibraryOverrideTestCase):
    """
    Tests that custom policies are loaded and respected.
    """

    _library = "library_business_logic_suite_managementPolicy_custom.json"

    __read_trait_sets = (
        {"definitely", "unique"},
        {"an", "ignored", "trait", "set"},
        {"a", "non", "exclusive", "trait", "set"},
    )

    __write_trait_sets = (
        {"definitely", "unique"},
        {"a", "managed", "trait", "set"},
    )

    def test_returns_expected_policies_for_all_trait_sets(self):
        context = self.createTestContext()
        expected = [
            TraitsData({"bal:test.SomePolicy"}),
            TraitsData(),
            TraitsData({"bal:test.SomePolicy"}),
        ]
        expected[0].setTraitProperty("bal:test.SomePolicy", "exclusive", True)

        actual = self._manager.managementPolicy(
            self.__read_trait_sets, PolicyAccess.kRead, context
        )

        self.assertListEqual(actual, expected)

    def test_returns_expected_policy_for_write_for_all_trait_sets(self):
        context = self.createTestContext()
        expected = [TraitsData(), TraitsData({"bal:test.SomePolicy"})]

        actual = self._manager.managementPolicy(
            self.__write_trait_sets, PolicyAccess.kWrite, context
        )

        self.assertListEqual(actual, expected)

    def test_returns_expected_policy_for_createRelated_for_all_trait_sets(self):
        context = self.createTestContext()
        expected = [TraitsData(), TraitsData({"bal:test.SomePolicy"})]

        actual = self._manager.managementPolicy(
            self.__write_trait_sets, PolicyAccess.kCreateRelated, context
        )

        self.assertListEqual(actual, expected)

    def test_returns_expected_policy_for_required_for_all_trait_sets(self):
        context = self.createTestContext()
        expected = [TraitsData(), TraitsData({"bal:test.SomePolicy"})]

        actual = self._manager.managementPolicy(
            self.__write_trait_sets, PolicyAccess.kRequired, context
        )

        self.assertListEqual(actual, expected)

    def test_returns_expected_policy_for_managerDriven_for_all_trait_sets(self):
        context = self.createTestContext()
        expected = [TraitsData(), TraitsData({"bal:test.SomePolicy"})]

        actual = self._manager.managementPolicy(
            self.__write_trait_sets, PolicyAccess.kManagerDriven, context
        )

        self.assertListEqual(actual, expected)


class Test_hasCapability_default(FixtureAugmentedTestCase):
    """
    Tests that BAL reports expected capabilities
    """

    def test_when_hasCapability_called_then_expected_capabilities_reported(self):
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kStatefulContexts))
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kCustomTerminology))

        self.assertTrue(self._manager.hasCapability(Manager.Capability.kResolution))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kPublishing))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kRelationshipQueries))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kExistenceQueries))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kDefaultEntityReferences))

    def test_when_hasCapability_called_on_managerInterface_then_has_mandatory_capabilities(self):
        interface = BasicAssetLibraryInterface()
        self.assertTrue(
            interface.hasCapability(ManagerInterface.Capability.kEntityReferenceIdentification)
        )
        self.assertTrue(
            interface.hasCapability(ManagerInterface.Capability.kManagementPolicyQueries)
        )


class Test_hasCapability_override_none(LibraryOverrideTestCase):
    _library = "library_business_logic_suite_capabilities_none.json"

    def setUp(self):
        # Override base class because otherwise it'll raise. The setUp
        # in this case _is_ the test.
        pass

    def test_when_when_library_lists_no_capabilities_then_raises(self):
        with self.assertRaises(ConfigurationException) as exc:
            # Call base class setup, which will re-initialize the
            # manager with the alternative self._library JSON file.
            super().setUp()

        self.assertEqual(
            str(exc.exception),
            "Manager implementation for 'org.openassetio.examples.manager.bal' does not"
            " support the required capabilities: entityReferenceIdentification,"
            " managementPolicyQueries, entityTraitIntrospection",
        )


class Test_hasCapability_override_all(LibraryOverrideTestCase):
    _library = "library_business_logic_suite_capabilities_all.json"

    def test_when_library_lists_all_capabilities_then_hasCapability_is_true_for_all(self):
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kStatefulContexts))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kCustomTerminology))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kDefaultEntityReferences))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kResolution))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kPublishing))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kRelationshipQueries))
        self.assertTrue(self._manager.hasCapability(Manager.Capability.kExistenceQueries))


class Test_hasCapability_override_minimal(LibraryOverrideTestCase):
    _library = "library_business_logic_suite_capabilities_minimal.json"

    def test_when_library_lists_minimal_capabilities_then_hasCapability_is_false_for_all(self):
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kStatefulContexts))
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kCustomTerminology))
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kDefaultEntityReferences))
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kResolution))
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kPublishing))
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kRelationshipQueries))
        self.assertFalse(self._manager.hasCapability(Manager.Capability.kExistenceQueries))

    def test_when_capability_not_supported_then_methods_raise_NotImplementedException(self):
        context = self.createTestContext()

        with self.assertRaises(NotImplementedException):
            self._manager.defaultEntityReference(
                [],
                DefaultEntityAccess.kRead,
                context,
                lambda *a: self.fail("Unexpected success"),
                lambda *a: self.fail("Unexpected element error"),
            )

        with self.assertRaises(NotImplementedException):
            self._manager.updateTerminology({})

        with self.assertRaises(NotImplementedException):
            self._manager.resolve([], set(), ResolveAccess.kRead, context)

        with self.assertRaises(NotImplementedException):
            self._manager.preflight([], [], PublishingAccess.kWrite, context)

        with self.assertRaises(NotImplementedException):
            self._manager.register([], [], PublishingAccess.kWrite, context)

        with self.assertRaises(NotImplementedException):
            self._manager.getWithRelationship(
                [], TraitsData(), 1, RelationsAccess.kRead, context, set()
            )

        with self.assertRaises(NotImplementedException):
            self._manager.getWithRelationships(
                self._manager.createEntityReference("bal:///"),
                [],
                1,
                RelationsAccess.kRead,
                context,
                set(),
            )

        with self.assertRaises(NotImplementedException):
            self._manager.entityExists([], context)


class Test_entityTraits(FixtureAugmentedTestCase):
    def test_when_missing_entity_queried_for_write_then_empty_trait_set_returned(self):
        # Missing entities are writable with unrestricted trait set.

        results = [None]

        self._manager.entityTraits(
            [self._manager.createEntityReference("bal:///some/new/ref")],
            EntityTraitsAccess.kWrite,
            self.createTestContext(),
            lambda idx, value: operator.setitem(results, idx, value),
            lambda idx, error: self.fail("entityTraits should not fail"),
        )
        [result] = results

        self.assertSetEqual(result, set())

    def test_when_existing_entity_queried_for_read_then_VersionTrait_imbued(self):
        # Missing entities are writable with unrestricted trait set.

        results = [None]

        self._manager.entityTraits(
            [self._manager.createEntityReference("bal:///entity/source")],
            EntityTraitsAccess.kRead,
            self.createTestContext(),
            lambda idx, value: operator.setitem(results, idx, value),
            lambda idx, error: self.fail("entityTraits should not fail"),
        )
        [result] = results

        self.assertIn(VersionTrait.kId, result)

    def test_when_existing_entity_queried_for_write_then_VersionTrait_not_imbued(self):
        # Missing entities are writable with unrestricted trait set.

        results = [None]

        self._manager.entityTraits(
            [self._manager.createEntityReference("bal:///entity/source")],
            EntityTraitsAccess.kWrite,
            self.createTestContext(),
            lambda idx, value: operator.setitem(results, idx, value),
            lambda idx, error: self.fail("entityTraits should not fail"),
        )
        [result] = results

        self.assertNotIn(VersionTrait.kId, result)

    def test_traits_for_read_are_same_as_for_write_but_with_VersionTrait(self):
        # Missing entities are writable with unrestricted trait set.

        results = [None]

        self._manager.entityTraits(
            [self._manager.createEntityReference("bal:///anAsset⭐︎")],
            EntityTraitsAccess.kRead,
            self.createTestContext(),
            lambda idx, value: operator.setitem(results, idx, value),
            lambda idx, error: self.fail("entityTraits should not fail"),
        )
        [read_result] = results

        self._manager.entityTraits(
            [self._manager.createEntityReference("bal:///anAsset⭐︎")],
            EntityTraitsAccess.kWrite,
            self.createTestContext(),
            lambda idx, value: operator.setitem(results, idx, value),
            lambda idx, error: self.fail("entityTraits should not fail"),
        )
        [write_result] = results

        self.assertSetEqual(read_result, write_result | {VersionTrait.kId})

    def test_when_explicit_write_traits_then_those_traits_returned(self):
        ref = self._manager.createEntityReference(
            "bal:///an asset with required traits for publish"
        )
        context = self.createTestContext()

        read_results = [None]
        write_results = [None]

        self._manager.entityTraits(
            [ref],
            EntityTraitsAccess.kRead,
            context,
            lambda idx, value: operator.setitem(read_results, idx, value),
            lambda idx, error: self.fail("entityTraits should not fail"),
        )

        self._manager.entityTraits(
            [ref],
            EntityTraitsAccess.kWrite,
            context,
            lambda idx, value: operator.setitem(write_results, idx, value),
            lambda idx, error: self.fail("entityTraits should not fail"),
        )

        [read_traits] = read_results
        [write_traits] = write_results

        self.assertSetEqual(read_traits, {"string", "number", VersionTrait.kId})
        self.assertSetEqual(write_traits, {"number"})

    def test_when_read_only_entity_then_EntityAccessError_returned(self):
        ref = self._manager.createEntityReference("bal:///a read only asset")
        expected_result = BatchElementError(
            BatchElementError.ErrorCode.kEntityAccessError,
            "Entity 'a read only asset' is inaccessible for write",
        )
        context = self.createTestContext()

        results = [None]

        self._manager.entityTraits(
            [ref],
            EntityTraitsAccess.kWrite,
            context,
            lambda idx, value: self.fail("entityTraits should not succeed"),
            lambda idx, error: operator.setitem(results, idx, error),
        )

        [actual_result] = results

        self.assertEqual(actual_result, expected_result)


class Test_defaultEntityReference(FixtureAugmentedTestCase):
    """
    Tests for the defaultEntityReference method.

    Uses the `defaultEntities` entry in library_apiComplianceSuite.json.
    """

    def test_when_read_trait_set_known_then_expected_reference_returned(self):
        expected = [
            self._manager.createEntityReference("bal:///a_default_read_entity_for_a_and_b"),
            self._manager.createEntityReference("bal:///a_default_read_entity_for_b_and_c"),
        ]
        access = DefaultEntityAccess.kRead

        self.assert_expected_entity_refs_for_access(expected, access)

    def test_when_write_trait_set_known_then_expected_reference_returned(self):
        expected = [
            self._manager.createEntityReference("bal:///a_default_write_entity_for_a_and_b"),
            self._manager.createEntityReference("bal:///a_default_write_entity_for_b_and_c"),
        ]
        access = DefaultEntityAccess.kWrite

        self.assert_expected_entity_refs_for_access(expected, access)

    def test_when_createRelated_trait_set_known_then_expected_reference_returned(self):
        expected = [
            self._manager.createEntityReference("bal:///a_default_relatable_entity_for_a_and_b"),
            self._manager.createEntityReference("bal:///a_default_relatable_entity_for_b_and_c"),
        ]
        access = DefaultEntityAccess.kCreateRelated

        self.assert_expected_entity_refs_for_access(expected, access)

    def test_when_no_default_then_entity_ref_is_None(self):
        results = [0]  # Don't initialise to None because that's the value we expect.

        self._manager.defaultEntityReference(
            [{"c", "d"}],
            DefaultEntityAccess.kRead,
            self.createTestContext(),
            lambda idx, value: operator.setitem(results, idx, value),
            lambda idx, error: self.fail("defaultEntityReference should not fail"),
        )

        [actual] = results

        self.assertIsNone(actual)

    def test_when_trait_set_not_known_then_InvalidTraitSet_error(self):
        results = [None]

        self._manager.defaultEntityReference(
            [{"a", "b", "c"}],
            DefaultEntityAccess.kRead,
            self.createTestContext(),
            lambda idx, value: self.fail("defaultEntityReference should not succeed"),
            lambda idx, error: operator.setitem(results, idx, error),
        )

        [actual] = results

        self.assertIsInstance(actual, BatchElementError)
        self.assertEqual(actual.code, BatchElementError.ErrorCode.kInvalidTraitSet)
        self.assertRegex(actual.message, r"^Unknown trait set {'[abc]', '[abc]', '[abc]'}")

    def assert_expected_entity_refs_for_access(self, expected, access):
        actual = [None, None]

        self._manager.defaultEntityReference(
            [{"a", "b"}, {"b", "c"}],
            access,
            self.createTestContext(),
            lambda idx, value: operator.setitem(actual, idx, value),
            lambda idx, error: self.fail("defaultEntityReference should not fail"),
        )

        self.assertEqual(actual, expected)


class Test_resolve(FixtureAugmentedTestCase):
    """
    Tests that resolution returns the expected values.
    """

    __entities = {
        "bal:///anAsset⭐︎": {
            "string": {"value": "resolved from 'anAsset⭐︎' version 2 using 📠"},
            "number": {"value": 28390222293},
            "test-data": {},
        },
        "bal:///another 𝓐𝓼𝓼𝓼𝓮𝔱": {
            "string": {"value": "resolved from 'another 𝓐𝓼𝓼𝓼𝓮𝔱' with a 📟"},
            "number": {},
        },
    }

    def test_when_refs_found_then_success_callback_called_with_expected_values(self):
        entity_references = [
            self._manager.createEntityReference(ref_str) for ref_str in self.__entities
        ]
        trait_set = {"string", "number", "test-data"}
        context = self.createTestContext()

        expected_results = []
        for entity_dict in self.__entities.values():
            expected_result = TraitsData()
            for trait_id, trait_properties in entity_dict.items():
                # Note: deliberately not imbuing traits with no
                # properties, as per API docs.
                for property_key, property_value in trait_properties.items():
                    expected_result.setTraitProperty(trait_id, property_key, property_value)
            expected_results.append(expected_result)

        actual_results = [None] * len(entity_references)

        def success_cb(idx, traits_data):
            actual_results[idx] = traits_data

        def error_cb(idx, batchElementError):
            self.fail(
                f"Unexpected error for '{entity_references[idx].toString()}':"
                f" {batchElementError.message}"
            )

        self._manager.resolve(
            entity_references, trait_set, ResolveAccess.kRead, context, success_cb, error_cb
        )

        self.assertEqual(actual_results, expected_results)

    def test_when_entity_has_no_versions_then_EntityResolutionError(self):
        expected = BatchElementError(
            BatchElementError.ErrorCode.kEntityResolutionError,
            "Entity 'an asset with no versions' does not have a version 1",
        )

        actual = self._manager.resolve(
            self._manager.createEntityReference("bal:///an asset with no versions"),
            set(),
            ResolveAccess.kRead,
            self.createTestContext(),
            self._manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual, expected)

    def test_when_implicitly_supported_access_then_can_resolve_access(self):
        trait_set = {"string", "wont-resolve"}
        expected = TraitsData({"string"})
        # Kludge to satisfy black formatting difference at exactly 99
        # chars on CI vs. local. Unicode shenanigans?
        expected_property_value = "resolved from 'anAsset⭐︎' version 2 using 📠"
        expected.setTraitProperty("string", "value", expected_property_value)
        context = self.createTestContext()

        actual = self._manager.resolve(
            self._manager.createEntityReference("bal:///anAsset⭐︎"),
            trait_set,
            ResolveAccess.kManagerDriven,
            context,
        )

        self.assertEqual(actual, expected)

    def test_when_explicitly_supported_access_then_can_resolve_supported_access(self):
        trait_set = {"string", "number", "test-data"}
        expected = TraitsData({"string"})
        expected.setTraitProperty("string", "value", "manager driven value")
        context = self.createTestContext()

        actual = self._manager.resolve(
            self._manager.createEntityReference("bal:///a manager driven asset"),
            trait_set,
            ResolveAccess.kManagerDriven,
            context,
        )

        self.assertEqual(actual, expected)

    def test_when_access_null_then_EntityResolutionError(self):
        trait_set = {"string", "number", "test-data"}
        expected = BatchElementError(
            BatchElementError.ErrorCode.kEntityResolutionError,
            "Entity 'a manager driven asset' does not have a version 1",
        )
        context = self.createTestContext()

        actual = self._manager.resolve(
            self._manager.createEntityReference("bal:///a manager driven asset"),
            trait_set,
            ResolveAccess.kRead,
            context,
            Manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual, expected)

    def test_when_access_blank_then_EntityAccessError(self):
        trait_set = {"string", "number", "test-data"}
        expected = BatchElementError(
            BatchElementError.ErrorCode.kEntityAccessError,
            "Entity 'a read only asset' is inaccessible for managerDriven",
        )
        context = self.createTestContext()

        actual = self._manager.resolve(
            self._manager.createEntityReference("bal:///a read only asset"),
            trait_set,
            ResolveAccess.kManagerDriven,
            context,
            Manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual, expected)


class Test_resolve_trait_property_expansion(LibraryOverrideTestCase):
    _library = "library_business_logic_suite_var_expansion.json"

    @mock.patch.dict(os.environ, {"CUSTOM": "the value from a custom"})
    def test_when_envvars_set_then_values_expanded_in_string_properties(self):
        expected = {
            # Check for consistency with os.path for HOME/UserProfile
            "HOME": os.path.expandvars("$HOME"),
            "UserProfile": os.path.expandvars("$UserProfile"),
            # Check custom vars set after the library was loaded
            "CUSTOM": "String with the value from a custom var",
        }
        data = self.__resolve_to_dict()
        for key, value in expected.items():
            self.assertEqual(data[key], value)

    def test_when_envvar_missing_then_value_unchanged_in_string_properties(self):
        data = self.__resolve_to_dict()
        self.assertEqual(data["MISSING"], "A $MISSING var")

    def test_when_properties_contain_no_substitutions_then_values_unchanged(self):
        expected = {"none": "No vars in string", "anInt": 3, "aBool": True}
        data = self.__resolve_to_dict()
        for key, value in expected.items():
            self.assertEqual(data[key], value)

    def test_when_bal_library_path_used_then_expanded_to_library_path(self):
        expected_path = os.path.join(os.path.dirname(__file__), "resources", self._library)
        data = self.__resolve_to_dict()
        self.assertEqual(data["bal_library_path"], f"Library is {expected_path}")

    def test_when_bal_library_dir_used_then_expanded_to_library_directory(self):
        expected_dir = os.path.join(os.path.dirname(__file__), "resources")
        data = self.__resolve_to_dict()
        self.assertEqual(data["bal_library_dir"], f"Library is in {expected_dir}")

    def test_when_file_prefixed_but_not_url_then_regurgitated_unmodified(self):
        data = self.__resolve_to_dict()
        self.assertEqual(data["a_file_prefixed_non_url"], "file:\\")

    def test_when_raw_file_url_used_then_regurgitated_unmodified(self):
        data = self.__resolve_to_dict()
        self.assertEqual(data["a_raw_posix_file_url"], "file:///mnt/per%2520cent")
        self.assertEqual(data["a_raw_windows_drive_file_url"], "file:///C:/per%2520cent")
        self.assertEqual(
            data["a_raw_windows_unc_file_url"], "file://hostname/sharename/per%2520cent"
        )

    def test_when_bal_library_url_used_then_expanded_to_library_directory(self):
        expected_url = pathlib.Path(__file__).with_name("resources").as_uri()
        data = self.__resolve_to_dict()
        self.assertEqual(data["bal_library_dir_url"], f"Library is in {expected_url}")

    def test_when_relative_bal_library_dir_used_then_library_path_not_normalized(self):
        # This just confirms existing behaviour when we put in url
        # normalization, and isn't so much a statement that paths should
        # not be normalized ... maybe they should be. We simply just
        # didn't have a need to do that at the time.
        expected_path = os.path.join(os.path.dirname(__file__), "resources/../above%20File.txt")
        data = self.__resolve_to_dict()
        self.assertEqual(data["relative_to_bal_library_dir"], expected_path)

    def test_when_relative_bal_library_dir_url_used_then_library_path_normalized(self):
        # Input path is "${bal_library_dir_url}/../above%2520File.txt",
        # folder structure is tests/resources
        # This test __file__ is in the `tests` dir.
        expected_url = pathlib.Path(__file__).with_name("above%20File.txt").as_uri()

        data = self.__resolve_to_dict()
        self.assertEqual(data["relative_to_bal_library_dir_url"], expected_url)

    def test_bal_library_dir_path_from_url_compatible(self):
        # Note that FileUrlPathConverter will %-decode the %2520 to %20.
        expected_path = os.path.join(os.path.dirname(__file__), "above%20File.txt")
        converter = FileUrlPathConverter()
        data = self.__resolve_to_dict()
        substituted_url = data["relative_to_bal_library_dir_url"]
        path = converter.pathFromUrl(substituted_url)
        self.assertEqual(path, expected_path)

    def test_when_custom_library_var_used_then_expanded_to_its_value(self):
        data = self.__resolve_to_dict()
        self.assertEqual(data["aLibraryVar"], "Value defined in the JSON")

    def __resolve_to_dict(self):
        """
        Grabs the data for a known entity/trait as a dict. We really
        need to write those convenience methods in the core API!
        """

        entity_ref = self._manager.createEntityReference("bal:///entity")
        trait_id = "aTrait"

        data = {}

        def success_cb(_, traits_data):
            data.update(
                {
                    key: traits_data.getTraitProperty(trait_id, key)
                    for key in traits_data.traitPropertyKeys(trait_id)
                }
            )

        def error_cb(_, batchElementError):
            self.fail(f"Unexpected error:" f" {batchElementError.message}")

        context = self.createTestContext()
        self._manager.resolve(
            [entity_ref], {trait_id}, ResolveAccess.kRead, context, success_cb, error_cb
        )

        return data


class Test_entityExists_version_query_param(FixtureAugmentedTestCase):
    def test_when_v_is_not_set_and_entity_exists_then_returns_true(self):
        self.assertEntityExists("anAsset⭐︎", None, True)

    def test_when_v_is_valid_then_true_returned(self):
        for i in range(1, 3):
            with self.subTest(v=i):
                self.assertEntityExists("anAsset⭐︎", f"{i}", True)

    def test_when_v_is_the_string_latest_then_true_returned(self):
        self.assertEntityExists("anAsset⭐︎", "latest", True)

    def test_when_v_is_greater_than_latest_then_false_returned(self):
        self.assertEntityExists("anAsset⭐︎", "3", False)

    def test_when_v_is_greater_less_than_one_then_false_returned(self):
        self.assertEntityExists("anAsset⭐︎", "3", False)

    def test_when_v_is_not_an_int_then_batch_element_error_is_returned(self):
        self.assertMalformedReferenceError(
            "anAsset⭐︎", "cabbage", "Version query parameter 'v' must be an int or 'latest'"
        )

    def test_when_v_is_less_than_one_then_batch_element_error_is_returned(self):
        self.assertMalformedReferenceError(
            "anAsset⭐︎", -3, "Version query parameter 'v' must be greater than 1"
        )

    def assertMalformedReferenceError(self, entity_name, specified_tag, expected_msg):
        """
        Asserts that the expected error is returned for an invalid tag.
        """

        ref_str = f"bal:///{entity_name}?v={specified_tag}"
        expceted_error = BatchElementError(
            BatchElementError.ErrorCode.kMalformedEntityReference,
            f"{expected_msg} ({ref_str})",
        )

        self._manager.entityExists(
            [self._manager.createEntityReference(ref_str)],
            self.createTestContext(),
            lambda idx, _: self.fail("Invalid references should trigger error callback"),
            lambda idx, error: self.assertEqual(error, expceted_error),
        )

    def assertEntityExists(self, entity_name, specified_tag, expected_exists):
        """
        Assets that the value of entityExists for the specified
        entity/version.
        """

        ref_str = f"bal:///{entity_name}"
        if specified_tag:
            ref_str += f"?v={specified_tag}"

        self._manager.entityExists(
            [self._manager.createEntityReference(ref_str)],
            self.createTestContext(),
            lambda idx, exists: self.assertEqual(exists, expected_exists),
            lambda idx, error: self.fail(
                f"Failed to check existence of reference: {error.message}"
            ),
        )


class Test_resolve_version_query_param(FixtureAugmentedTestCase):
    def test_when_v_is_not_set_latest_is_resolved_with_version_trait(self):
        self.assertVersioning("anAsset⭐︎", None, "2")

    def test_when_v_is_valid_integer_corresponding_entity_resolved_with_version_trait(self):
        self.assertVersioning("anAsset⭐︎", "1", "1")

    def test_when_v_is_the_string_latest_then_latest_is_resolved_with_version_trait(self):
        self.assertVersioning("anAsset⭐︎", "latest", "2")

    def test_when_v_is_greater_than_latest_then_resolution_error_returned(self):
        with self.assertRaises(BatchElementException):
            self.assertVersioning("anAsset⭐︎", "3", "")

    def test_when_v_is_less_than_one_then_resolution_error_returned(self):
        with self.assertRaises(BatchElementException):
            self.assertVersioning("anAsset⭐︎", "0", "")

    def test_when_v_is_not_an_integer_then_error_is_returned(self):
        with self.assertRaises(BatchElementException):
            self.assertVersioning("anAsset⭐︎", "cabbage", "")

    def assertVersioning(self, entity_name, specified_tag, expected_stable):
        """
        Asserts the correct entity has been retrieved and the specified
        and stable tag properties are set correctly.
        """

        ref_str = f"bal:///{entity_name}"
        if specified_tag:
            ref_str += f"?v={specified_tag}"

        data = self._manager.resolve(
            self._manager.createEntityReference(ref_str),
            {"expected-version", VersionTrait.kId},
            ResolveAccess.kRead,
            self.createTestContext(),
        )

        self.assertEqual(data.getTraitProperty("expected-version", "tag"), expected_stable)

        version_trait = openassetio_mediacreation.traits.lifecycle.VersionTrait(data)
        self.assertEqual(version_trait.getSpecifiedTag(), specified_tag or "latest")
        self.assertEqual(version_trait.getStableTag(), expected_stable)


class Test_getWithRelationship_access(GetWithRelationshipTestCase):
    def test_when_access_mode_matches_default_then_expected_relations_returned(self):
        input_ref = self._manager.createEntityReference("bal:///entity/original")
        expected_refs = [
            self._manager.createEntityReference("bal:///entity/proxy/1"),
            self._manager.createEntityReference("bal:///entity/proxy/2"),
            self._manager.createEntityReference("bal:///entity/proxy/3"),
        ]
        # No "access" provided for "proxy" relationship in library, so kRead assumed.
        self.assertExpectedRefs(
            input_ref, TraitsData({"proxy"}), expected_refs, access=RelationsAccess.kRead
        )

    def test_when_access_mode_doesnt_match_default_then_no_relations_returned(self):
        input_ref = self._manager.createEntityReference("bal:///entity/original")
        expected_refs = []
        # No "access" provided for "proxy" relationship in library, so kRead assumed.
        self.assertExpectedRefs(
            input_ref, TraitsData({"proxy"}), expected_refs, access=RelationsAccess.kWrite
        )

    def test_when_access_mode_matches_override_then_expected_relation_returned(self):
        input_ref = self._manager.createEntityReference("bal:///entity/original")
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎")]
        # Explicit kWrite "access" provided for "publishable" relationship in library.
        self.assertExpectedRefs(
            input_ref, TraitsData({"publishable"}), expected_refs, access=RelationsAccess.kWrite
        )

    def test_when_access_mode_doesnt_match_override_then_no_relations_returned(self):
        input_ref = self._manager.createEntityReference("bal:///entity/original")
        expected_refs = []
        # Explicit kWrite "access" provided for "publishable" relationship in library.
        self.assertExpectedRefs(
            input_ref, TraitsData({"publishable"}), expected_refs, access=RelationsAccess.kRead
        )


class Test_preflight(FixtureAugmentedTestCase):
    def test_when_refs_contains_no_version_then_passed_through_unchanged(self):
        entity_references = [
            self._manager.createEntityReference(s)
            for s in ["bal:///A ref to a 🐔", "bal:///anotherRef"]
        ]
        traits_datas = [TraitsData()] * len(entity_references)
        context = self.createTestContext()

        result_references = [None] * len(entity_references)

        self._manager.preflight(
            entity_references,
            traits_datas,
            PublishingAccess.kWrite,
            context,
            lambda idx, ref: operator.setitem(result_references, idx, ref),
            lambda _idx, _err: self.fail("Preflight should not error for this input"),
        )

        self.assertEqual(result_references, entity_references)

    def test_when_unsupported_access_then_kEntityAccessError_returned(self):
        entity_references = [self._manager.createEntityReference("bal:///something/new")]

        expected = [
            BatchElementError(
                BatchElementError.ErrorCode.kEntityAccessError,
                "Unsupported access mode for preflight",
            )
        ]

        actual = [None]

        self._manager.preflight(
            entity_references,
            [TraitsData()],
            PublishingAccess.kCreateRelated,
            self.createTestContext(),
            lambda _idx, _ref: self.fail("Preflight should not succeed for this input"),
            # pylint: disable=cell-var-from-loop
            lambda idx, err: operator.setitem(actual, idx, err),
        )

        self.assertListEqual(actual, expected)

    def test_when_refs_versioned_then_v_query_param_removed(self):
        entity_references = [
            self._manager.createEntityReference(s)
            for s in ["bal:///A ref to a 🐔?v=2", "bal:///anotherRef?v=6"]
        ]
        traits_datas = [TraitsData()] * len(entity_references)
        context = self.createTestContext()

        result_references = [None] * len(entity_references)

        self._manager.preflight(
            entity_references,
            traits_datas,
            PublishingAccess.kWrite,
            context,
            lambda idx, ref: operator.setitem(result_references, idx, ref),
            lambda _idx, _err: self.fail("Preflight should not error for this input"),
        )

        for ref in result_references:
            self.assertFalse("v=" in ref.toString())

    def test_when_unsupported_trait_set_then_InvalidTraitSet_returned(self):
        entity_ref = self._manager.createEntityReference("bal:///new")
        traits_data = TraitsData({"an", "ignored", "trait", "set"})
        expected_result = BatchElementError(
            BatchElementError.ErrorCode.kInvalidTraitSet,
            "Publishing is not supported for the given trait set",
        )

        actual_result = self._manager.preflight(
            entity_ref,
            traits_data,
            PublishingAccess.kWrite,
            self.createTestContext(),
            self._manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual_result, expected_result)

    def test_when_required_traits_for_entity_missing_then_InvalidTraitSet_returned(self):
        entity_ref = self._manager.createEntityReference(
            "bal:///an asset with required traits for publish"
        )
        traits_data = TraitsData({"string"})
        expected_result = BatchElementError(
            BatchElementError.ErrorCode.kInvalidTraitSet,
            "Publishing to this entity requires traits that are missing from the input",
        )

        actual_result = self._manager.preflight(
            entity_ref,
            traits_data,
            PublishingAccess.kWrite,
            self.createTestContext(),
            self._manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual_result, expected_result)

    def test_when_read_only_entity_then_EntityAccessError_returned(self):
        entity_ref = self._manager.createEntityReference("bal:///a read only asset")
        traits_data = TraitsData({"string"})
        expected_result = BatchElementError(
            BatchElementError.ErrorCode.kEntityAccessError,
            "Entity 'a read only asset' is inaccessible for write",
        )

        actual_result = self._manager.preflight(
            entity_ref,
            traits_data,
            PublishingAccess.kWrite,
            self.createTestContext(),
            self._manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual_result, expected_result)


class Test_register(FixtureAugmentedTestCase):
    def test_when_ref_is_new_then_entity_created_with_versioned_reference(self):
        context = self.createTestContext()
        data = TraitsData()
        data.setTraitProperty("a_trait", "a_property", 1)
        new_entity_ref = self._manager.createEntityReference(
            "bal:///test_when_ref_is_new_then_entity_created_with_same_reference"
        )
        published_entity_ref = self.__create_test_entity(new_entity_ref, data, context)

        self._manager.entityExists(
            [published_entity_ref],
            context,
            lambda idx, exists: self.assertTrue(exists),
            lambda idx, error: self.fail(
                f"Failed to check existence of reference: {error.message}"
            ),
        )

        expected_entity_ref = self._manager.createEntityReference(
            "bal:///test_when_ref_is_new_then_entity_created_with_same_reference?v=1"
        )

        self.assertEqual(expected_entity_ref, published_entity_ref)

    def test_when_ref_exists_then_entity_updated_with_versioned_reference(self):
        context = self.createTestContext()
        data = TraitsData()
        data.setTraitProperty("a_trait", "a_property", 1)

        test_entity_ref = self._manager.createEntityReference(
            "bal:///test_when_ref_exsits_then_entity_updated_with_same_reference"
        )
        existing_entity_ref = self.__create_test_entity(test_entity_ref, data, context)

        original_data = TraitsData(data)
        data.setTraitProperty("a_trait", "a_property", 2)

        updated_refs = [None]

        self._manager.register(
            [existing_entity_ref],
            [data],
            PublishingAccess.kWrite,
            context,
            lambda idx, ref: operator.setitem(updated_refs, idx, ref),
            lambda _, err: self.fail(f"Register should not error: {err.code} {err.message}"),
        )

        expected_entity_ref = self._manager.createEntityReference(
            "bal:///test_when_ref_exsits_then_entity_updated_with_same_reference?v=2"
        )

        self.assertEqual(updated_refs[0], expected_entity_ref)

        resolved_data = [None]

        self._manager.resolve(
            updated_refs,
            {"a_trait"},
            ResolveAccess.kRead,
            context,
            lambda idx, data: operator.setitem(resolved_data, idx, data),
            lambda _, err: self.fail(f"Resolve should not error: {err.code} {err.message}"),
        )

        self.assertEqual(resolved_data[0], data)
        self.assertNotEqual(resolved_data[0], original_data)

    def test_when_unsupported_access_then_kEntityAccessError_returned(self):
        entity_references = [self._manager.createEntityReference("bal:///something/new")]

        expected = [
            BatchElementError(
                BatchElementError.ErrorCode.kEntityAccessError,
                "Unsupported access mode for register",
            )
        ]

        actual = [None]
        context = self.createTestContext()

        self._manager.register(
            entity_references,
            [TraitsData()],
            PublishingAccess.kCreateRelated,
            context,
            lambda _idx, _ref: self.fail("Register should not succeed for this input"),
            # pylint: disable=cell-var-from-loop
            lambda idx, err: operator.setitem(actual, idx, err),
        )

        self.assertListEqual(actual, expected)

    def __create_test_entity(self, ref, data, context):
        """
        Creates a new entity in the library for testing.
        Asserts that the entity does not exist prior to creation.
        """
        self._manager.entityExists(
            [ref],
            context,
            lambda idx, exists: self.assertFalse(
                exists, f"Entity '{ref.toString()}' already exists"
            ),
            lambda idx, error: self.fail(
                f"Failed to check existence of reference: {error.message}"
            ),
        )

        published_refs = [None]

        self._manager.register(
            [ref],
            [data],
            PublishingAccess.kWrite,
            context,
            lambda idx, published_ref: operator.setitem(published_refs, idx, published_ref),
            lambda _, err: self.fail(f"Failed to create new entity: {err.code} {err.message}"),
        )

        return published_refs[0]

    def test_when_unsupported_trait_set_then_InvalidTraitSet_returned(self):
        entity_ref = self._manager.createEntityReference("bal:///new")
        traits_data = TraitsData({"an", "ignored", "trait", "set"})
        expected_result = BatchElementError(
            BatchElementError.ErrorCode.kInvalidTraitSet,
            "Publishing is not supported for the given trait set",
        )

        actual_result = self._manager.register(
            entity_ref,
            traits_data,
            PublishingAccess.kWrite,
            self.createTestContext(),
            self._manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual_result, expected_result)

    def test_when_required_traits_for_entity_missing_then_InvalidTraitSet_returned(self):
        entity_ref = self._manager.createEntityReference(
            "bal:///an asset with required traits for publish"
        )
        traits_data = TraitsData({"string"})
        expected_result = BatchElementError(
            BatchElementError.ErrorCode.kInvalidTraitSet,
            "Publishing to this entity requires traits that are missing from the input",
        )

        actual_result = self._manager.register(
            entity_ref,
            traits_data,
            PublishingAccess.kWrite,
            self.createTestContext(),
            self._manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual_result, expected_result)

    def test_when_read_only_entity_then_EntityAccessError_returned(self):
        entity_ref = self._manager.createEntityReference("bal:///a read only asset")
        traits_data = TraitsData({"string"})
        expected_result = BatchElementError(
            BatchElementError.ErrorCode.kEntityAccessError,
            "Entity 'a read only asset' is inaccessible for write",
        )

        actual_result = self._manager.register(
            entity_ref,
            traits_data,
            PublishingAccess.kWrite,
            self.createTestContext(),
            self._manager.BatchElementErrorPolicyTag.kVariant,
        )

        self.assertEqual(actual_result, expected_result)


class Test_getWithRelationship_versions(GetWithRelationshipTestCase):
    def test_when_querying_versions_then_versions_and_latest_returned(self):
        expected_refs = [
            self._manager.createEntityReference(r)
            for r in (
                "bal:///anAsset⭐︎",
                "bal:///anAsset⭐︎?v=2",
                "bal:///anAsset⭐︎?v=1",
            )
        ]
        self.assertExpectedVersionRefs(EntityVersionsRelationshipSpecification, expected_refs)

    def test_when_querying_stable_versions_then_versions_returned(self):
        expected_refs = [
            self._manager.createEntityReference(r)
            for r in (
                "bal:///anAsset⭐︎?v=2",
                "bal:///anAsset⭐︎?v=1",
            )
        ]
        self.assertExpectedVersionRefs(
            StableEntityVersionsRelationshipSpecification, expected_refs
        )

    def test_when_querying_specified_version_then_version_returned(self):
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎?v=1")]
        self.assertExpectedVersionRefs(EntityVersionsRelationshipSpecification, expected_refs, "1")

    def test_when_querying_specified_stable_version_then_version_returned(self):
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎?v=1")]
        self.assertExpectedVersionRefs(
            StableEntityVersionsRelationshipSpecification, expected_refs, "1"
        )

    def test_when_querying_latest_version_then_unversioned_ref_returned(self):
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎")]
        self.assertExpectedVersionRefs(
            EntityVersionsRelationshipSpecification, expected_refs, "latest"
        )

    def test_when_querying_latest_stable_version_then_version_returned(self):
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎?v=2")]
        self.assertExpectedVersionRefs(
            StableEntityVersionsRelationshipSpecification, expected_refs, "latest"
        )

    def assertExpectedVersionRefs(self, specification, expected_refs, specify_version=None):
        relationship = specification.create().traitsData()
        if specify_version:
            VersionTrait(relationship).setSpecifiedTag(specify_version)
        ref = self._manager.createEntityReference("bal:///anAsset⭐︎")
        self.assertExpectedRefs(ref, relationship, expected_refs)


class Test_getWithRelationship_stable_ref(GetWithRelationshipTestCase):
    def test_when_querying_unversioned_reference_then_v2_ref_returned(self):
        input_ref = self._manager.createEntityReference("bal:///anAsset⭐︎")
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎?v=2")]
        self.assertExpectedRefs(
            input_ref,
            StableReferenceRelationshipSpecification.create().traitsData(),
            expected_refs,
        )

    def test_when_querying_latest_reference_then_v2_ref_returned(self):
        input_ref = self._manager.createEntityReference("bal:///anAsset⭐︎?v=latest")
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎?v=2")]
        self.assertExpectedRefs(
            input_ref,
            StableReferenceRelationshipSpecification.create().traitsData(),
            expected_refs,
        )

    def test_when_querying_v1_reference_then_v1_ref_returned(self):
        input_ref = self._manager.createEntityReference("bal:///anAsset⭐︎?v=1")
        expected_refs = [self._manager.createEntityReference("bal:///anAsset⭐︎?v=1")]
        self.assertExpectedRefs(
            input_ref,
            StableReferenceRelationshipSpecification.create().traitsData(),
            expected_refs,
        )


class Test_getWithRelationship_override_version(GetWithRelationshipTestCase):

    def test_when_relationship_overrides_default_versioning_behaviour_then_override_returned(self):
        """
        By default, BAL handles version relationships as a special case (for better or worse). But
        we offer a way to override that behaviour using the data-driven approach used for other
        types of query, i.e. by explicitly defining a version relationship in the JSON library.
        """
        input_ref = self._manager.createEntityReference("bal:///entity/original")
        expected_refs = [self._manager.createEntityReference("bal:///another 𝓐𝓼𝓼𝓼𝓮𝔱")]
        self.assertExpectedRefs(
            input_ref,
            EntityVersionsRelationshipSpecification.create().traitsData(),
            expected_refs,
        )


def resources_path():
    return os.path.join(os.path.dirname(__file__), "resources")
