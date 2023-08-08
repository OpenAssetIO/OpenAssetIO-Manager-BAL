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

# pylint: disable=invalid-name, missing-function-docstring, missing-class-docstring

import operator
import os

from unittest import mock

from openassetio import constants, Context, TraitsData
from openassetio.exceptions import PluginError
from openassetio.test.manager.harness import FixtureAugmentedTestCase


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
        self._manager.initialize(new_settings)
        self.addCleanup(self.cleanUp)

    def cleanUp(self):
        self._manager.initialize(self.__old_settings)


class Test_initialize_library_path(FixtureAugmentedTestCase):
    shareManager = False

    alt_lib_path = os.path.join(os.path.dirname(__file__), "resources", "library_empty.json")

    @mock.patch.dict(os.environ)
    def test_when_setting_and_env_not_set_then_PluginError_raised(self):
        if LIBRARY_PATH_VARNAME in os.environ:
            del os.environ[LIBRARY_PATH_VARNAME]
        with self.assertRaises(PluginError):
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
    def test_when_setting_and_env_blank_then_PluginError_raised(self):
        os.environ[LIBRARY_PATH_VARNAME] = ""
        with self.assertRaises(PluginError):
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
        self.assertTrue(self._manager.entityExists([ref], context)[0])

        # Assert prefix used to generate new references
        published_refs = [None]
        context.access = Context.Access.kWrite
        self._manager.register(
            [self._manager.createEntityReference(f"{prefix}a_new_entity_for_scheme_{scheme}")],
            [TraitsData({"someTrait"})],
            context,
            lambda idx, published_ref: operator.setitem(published_refs, idx, published_ref),
            lambda _, err: self.fail(f"Failed to create new entity: {err.code} {err.message}"),
        )
        self.assertTrue(str(published_refs[0]).startswith(prefix))


class Test_managementPolicy_missing_completely(LibraryOverrideTestCase):
    """
    Tests error case when  BAL library managementPolicy is missing.
    """

    _library = "library_business_logic_suite_blank.json"

    def test_when_read_policy_queried_from_library_with_no_policies_then_raises_exception(
        self,
    ):
        context = self.createTestContext(access=Context.Access.kRead)

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], context)

        self.assertEqual(
            str(ex.exception),
            "BAL library is missing a managementPolicy for 'read'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema.",
        )

    def test_when_write_policy_queried_from_library_with_no_policies_then_raises_exception(
        self,
    ):
        context = self.createTestContext(access=Context.Access.kWrite)

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], context)

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
        context = self.createTestContext(access=Context.Access.kRead)

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], context)

        self.assertEqual(
            str(ex.exception),
            "BAL library is missing a managementPolicy for 'read'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema.",
        )

    def test_when_write_policy_queried_from_library_missing_default_policy_then_raises_exception(
        self,
    ):
        context = self.createTestContext(access=Context.Access.kWrite)

        with self.assertRaises(LookupError) as ex:
            self._manager.managementPolicy([{"a trait"}], context)

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
        context = self.createTestContext(access=Context.Access.kRead)
        expected = [
            TraitsData({"bal:test.SomePolicy"}),
            TraitsData(),
            TraitsData({"bal:test.SomePolicy"}),
        ]
        expected[0].setTraitProperty("bal:test.SomePolicy", "exclusive", True)

        actual = self._manager.managementPolicy(self.__read_trait_sets, context)

        self.assertListEqual(actual, expected)

    def test_returns_expected_policy_for_write_for_all_trait_sets(self):
        context = self.createTestContext(access=Context.Access.kWrite)
        expected = [TraitsData(), TraitsData({"bal:test.SomePolicy"})]

        actual = self._manager.managementPolicy(self.__write_trait_sets, context)

        self.assertListEqual(actual, expected)


class Test_resolve(FixtureAugmentedTestCase):
    """
    Tests that resolution returns the expected values.
    """

    __entities = {
        "bal:///anAsset⭐︎": {
            "string": {"value": "resolved from 'anAsset⭐︎' using 📠"},
            "number": {"value": 42},
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
        context = self.createTestContext(access=Context.Access.kRead)

        results = [None] * len(entity_references)

        def success_cb(idx, traits_data):
            results[idx] = traits_data

        def error_cb(idx, batchElementError):
            self.fail(
                f"Unexpected error for '{entity_references[idx].toString()}':"
                f" {batchElementError.message}"
            )

        self._manager.resolve(entity_references, trait_set, context, success_cb, error_cb)

        for ref, result in zip(entity_references, results):
            # Check all traits are present, and their properties.
            # TODO(tc): When we have a better introspection API in
            # TraitsData, we can assert there aren't any bonus values.
            for trait in self.__entities[ref.toString()].keys():
                self.assertTrue(result.hasTrait(trait))
                for property_, value in self.__entities[ref.toString()][trait].items():
                    self.assertEqual(result.getTraitProperty(trait, property_), value)


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

        context = self.createTestContext(access=Context.Access.kRead)
        self._manager.resolve([entity_ref], {trait_id}, context, success_cb, error_cb)

        return data


class Test_preflight(FixtureAugmentedTestCase):
    def test_when_refs_valid_then_are_passed_through_unchanged(self):
        entity_references = [
            self._manager.createEntityReference(s)
            for s in ["bal:///A ref to a 🐔", "bal:///anotherRef"]
        ]
        traits_datas = [TraitsData()] * len(entity_references)
        context = self.createTestContext(access=Context.Access.kWrite)

        result_references = [None] * len(entity_references)

        self._manager.preflight(
            entity_references,
            traits_datas,
            context,
            lambda idx, ref: operator.setitem(result_references, idx, ref),
            lambda _idx, _err: self.fail("Preflight should not error for this input"),
        )

        self.assertEqual(result_references, entity_references)


class Test_register(FixtureAugmentedTestCase):
    def test_when_ref_is_new_then_entity_created_with_same_reference(self):
        context = self.createTestContext()
        data = TraitsData()
        data.setTraitProperty("a_trait", "a_property", 1)
        new_entity_ref = self._manager.createEntityReference(
            "bal:///test_when_ref_is_new_then_entity_created_with_same_reference"
        )
        published_entity_ref = self.__create_test_entity(new_entity_ref, data, context)

        context.access = Context.Access.kRead
        self.assertTrue(self._manager.entityExists([published_entity_ref], context)[0])
        self.assertEqual(published_entity_ref, new_entity_ref)

    def test_when_ref_exists_then_entity_updated_with_same_reference(self):
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

        context.access = Context.Access.kWrite
        self._manager.register(
            [existing_entity_ref],
            [data],
            context,
            lambda idx, ref: operator.setitem(updated_refs, idx, ref),
            lambda _, err: self.fail(f"Register should not error: {err.code} {err.message}"),
        )

        resolved_data = [None]

        context.access = Context.Access.kRead
        self._manager.resolve(
            updated_refs,
            {"a_trait"},
            context,
            lambda idx, data: operator.setitem(resolved_data, idx, data),
            lambda _, err: self.fail(f"Resolve should not error: {err.code} {err.message}"),
        )

        self.assertEqual(resolved_data[0], data)
        self.assertNotEqual(resolved_data[0], original_data)

    def __create_test_entity(self, ref, data, context):
        """
        Creates a new entity in the library for testing.
        Asserts that the entity does not exist prior to creation.
        """
        ## @TODO (tc) Resurrect "scoped context override"?
        old_access = context.access

        context.access = Context.Access.kRead
        self.assertFalse(
            self._manager.entityExists([ref], context)[0],
            f"Entity '{ref.toString()}' already exists",
        )

        published_refs = [None]

        context.access = Context.Access.kWrite
        self._manager.register(
            [ref],
            [data],
            context,
            lambda idx, published_ref: operator.setitem(published_refs, idx, published_ref),
            lambda _, err: self.fail(f"Failed to create new entity: {err.code} {err.message}"),
        )

        context.access = old_access
        return published_refs[0]


def resources_path():
    return os.path.join(os.path.dirname(__file__), "resources")
