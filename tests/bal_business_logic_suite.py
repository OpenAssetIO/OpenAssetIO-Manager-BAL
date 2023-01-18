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

from openassetio import Context, TraitsData
from openassetio.test.manager.harness import FixtureAugmentedTestCase


__all__ = []


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


class Test_preflight(FixtureAugmentedTestCase):
    def test_when_refs_valid_then_are_passed_through_unchanged(self):
        entity_references = [
            self._manager.createEntityReference(s)
            for s in ["bal:///A ref to a 🐔", "bal:///anotherRef"]
        ]
        trait_set = {"a_trait", "another_trait"}
        context = self.createTestContext(access=Context.Access.kWrite)

        result_references = [None] * len(entity_references)

        self._manager.preflight(
            entity_references,
            trait_set,
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


class Test_getRelatedRefrences(LibraryOverrideTestCase):

    # @TODO(tc) Switch to fixtures once covered by the OpenAssetIO
    # apiComplianceSuite as this should really be tested there. This
    # will be added when the C++ port happens along with the switch to
    # callback-based signatures.

    _library = "library_business_logic_suite_related_references.json"

    _proxy_trait_id = "proxy"
    _source_trait_id = "source"

    _proxy_relation = TraitsData({_proxy_trait_id})

    def __refs(self, *args):
        """
        Converts string args to entity references
        """
        return [self._manager.createEntityReference(ref_str) for ref_str in args]

    def test_when_called_with_no_relation_properties_then_all_matching_trait_set_returned(self):
        expected_refs = self.__refs(
            "bal:///entity/proxy/1",
            "bal:///entity/proxy/2",
            "bal:///entity/proxy/3",
        )

        result = self._manager.getRelatedReferences(
            self.__refs("bal:///entity/original"),
            [self._proxy_relation],
            self.createTestContext(access=Context.Access.kRead),
        )

        self.assertEqual(result, [expected_refs])

    def test_when_called_with_relation_properties_then_only_those_matching_traits_data_returned(
        self,
    ):
        expected_refs = self.__refs("bal:///entity/proxy/3")

        filtered_proxy_relation = TraitsData(self._proxy_relation)
        filtered_proxy_relation.setTraitProperty(self._proxy_trait_id, "type", "alt")

        result = self._manager.getRelatedReferences(
            self.__refs("bal:///entity/original"),
            [filtered_proxy_relation],
            self.createTestContext(access=Context.Access.kRead),
        )

        self.assertEqual(result, [expected_refs])

    def test_when_resultTraitSet_specified_then_only_those_containing_trait_set_returned(self):
        expected_refs = self.__refs("bal:///entity/proxy/2", "bal:///entity/proxy/3")

        result = self._manager.getRelatedReferences(
            self.__refs("bal:///entity/original"),
            [self._proxy_relation],
            self.createTestContext(access=Context.Access.kRead),
            resultTraitSet={"b"},
        )

        self.assertEqual(result, [expected_refs])

    def test_when_single_ref_and_multiple_relations_supplied_then_ref_is_used_for_all(self):
        expected_refs = [
            self.__refs("bal:///entity/proxy/1", "bal:///entity/proxy/2", "bal:///entity/proxy/3"),
            self.__refs("bal:///entity/source"),
        ]

        result = self._manager.getRelatedReferences(
            self.__refs("bal:///entity/original"),
            [self._proxy_relation, TraitsData({self._source_trait_id})],
            self.createTestContext(access=Context.Access.kRead),
        )

        self.assertEqual(result, expected_refs)

    def test_when_multiple_refs_and_single_relation_supplied_then_relation_us_used_for_all(self):
        expected_refs = [
            self.__refs("bal:///entity/proxy/1", "bal:///entity/proxy/2", "bal:///entity/proxy/3"),
            [],
        ]

        result = self._manager.getRelatedReferences(
            self.__refs("bal:///entity/original", "bal:///entity/source"),
            [self._proxy_relation],
            self.createTestContext(access=Context.Access.kRead),
        )

        self.assertEqual(result, expected_refs)

    def test_when_multiple_refs_and_relations_supplied_then_matched_index_wise(self):
        expected_refs = [
            self.__refs("bal:///entity/proxy/1", "bal:///entity/proxy/2", "bal:///entity/proxy/3"),
            self.__refs("bal:///entity/original"),
        ]

        result = self._manager.getRelatedReferences(
            self.__refs("bal:///entity/original", "bal:///entity/source"),
            [self._proxy_relation, TraitsData({"derived"})],
            self.createTestContext(access=Context.Access.kRead),
        )

        self.assertEqual(result, expected_refs)

    def test_when_relation_not_in_library_then_exception_raised(self):
        with self.assertRaises(RuntimeError) as ex:
            self._manager.getRelatedReferences(
                self.__refs("bal:///entity/original"),
                [TraitsData({"missing"})],
                self.createTestContext(access=Context.Access.kRead),
            )
        self.assertEqual(str(ex.exception), "Unknown BAL entity: 'missingEntity'")


class Test_getRelatedRefrences_relations_data_missing(FixtureAugmentedTestCase):
    def test_when_library_missing_relations_data_then_empty_result_is_returned(self):
        # The standard library has no relations data
        result = self._manager.getRelatedReferences(
            self._manager.createEntityReference("bal:///another 𝓐𝓼𝓼𝓼𝓮𝔱"),
            [TraitsData({"someTrait"})],
            self.createTestContext(access=Context.Access.kRead),
        )
        self.assertEqual(result, [[]])
