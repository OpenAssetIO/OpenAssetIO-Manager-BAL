#
#   Copyright 2013-2023 The Foundry Visionmongers Ltd
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
BasicAssetLibrary manager behaves as expected concerning functional
behaviors that don't fall under "business-logic", such as performance
related requirements.
"""
import contextlib
import operator

# pylint: disable=invalid-name, missing-function-docstring, missing-class-docstring

import os
from unittest import mock

from openassetio import TraitsData
from openassetio.access import PublishingAccess, RelationsAccess, ResolveAccess
from openassetio.test.manager.harness import FixtureAugmentedTestCase


class Test_simulated_latency_default(FixtureAugmentedTestCase):
    """
    Tests default settings values of an uninitialized manager.
    """

    shareManager = False

    def test_when_uninitialized_then_defaults_to_10ms(self):
        # Default of 10m is defined in bal.make_default_settings()
        self.assertEqual(self._manager.settings()["simulated_query_latency_ms"], 10)


class Test_simulated_latency(FixtureAugmentedTestCase):
    """
    Tests that check the simulated latency value causes time delay
    """

    def create_test_entity_references(self):
        return [
            self._manager.createEntityReference(ref_str)
            for ref_str in ["bal:///anAsset⭐︎", "bal:///another 𝓐𝓼𝓼𝓼𝓮𝔱"]
        ]

    __test_query_latencies = [0, 2500.5, 5000]

    def test_when_resolve_called_then_results_delayed_by_specified_simulated_query_latency(self):
        self.__check_simulated_latencies(
            self._manager.resolve,
            self.create_test_entity_references(),
            {"string"},
            ResolveAccess.kRead,
            self.createTestContext(),
        )

    def test_when_preflight_called_then_results_delayed_by_specified_simulated_query_latency(self):
        entity_references = self.create_test_entity_references()
        traits_datas = [TraitsData({"string"})] * len(entity_references)
        self.__check_simulated_latencies(
            self._manager.preflight,
            entity_references,
            traits_datas,
            PublishingAccess.kWrite,
            self.createTestContext(),
        )

    def test_when_entityExists_called_then_results_delayed_by_specified_simulated_query_latency(
        self,
    ):
        self.__check_simulated_latencies(
            self._manager.entityExists,
            self.create_test_entity_references(),
            self.createTestContext(),
        )

    def test_when_register_called_then_results_delayed_by_specified_simulated_query_latency(self):
        entity_refs = self.create_test_entity_references()
        traits_datas = [TraitsData() for _ in entity_refs]

        self.__check_simulated_latencies(
            self._manager.register,
            entity_refs,
            traits_datas,
            PublishingAccess.kWrite,
            self.createTestContext(),
        )

    def test_when_getWithRelationship_called_then_results_delayed_by_specified_query_latency(
        self,
    ):
        entity_refs = self.create_test_entity_references()

        self.__check_simulated_latencies(
            self._manager.getWithRelationship,
            entity_refs,
            TraitsData(),
            1,
            RelationsAccess.kRead,
            self.createTestContext(),
        )

    def test_when_getWithRelationships_called_then_results_delayed_by_specified_query_latency(
        self,
    ):
        entity_ref = self.create_test_entity_references()[0]
        traits_datas = [TraitsData()] * 3

        self.__check_simulated_latencies(
            self._manager.getWithRelationships,
            entity_ref,
            traits_datas,
            1,
            RelationsAccess.kRead,
            self.createTestContext(),
        )

    def test_when_pager_hasNext_called_then_results_delayed(
        self,
    ):
        for query_latency in self.__simulated_latency_subtests():
            pager = self.__create_pager()
            with self.__assert_simulated_latency_applied(query_latency):
                pager.hasNext()

    def test_when_pager_next_called_then_results_delayed(
        self,
    ):
        for query_latency in self.__simulated_latency_subtests():
            pager = self.__create_pager()
            with self.__assert_simulated_latency_applied(query_latency):
                pager.next()

    def test_when_pager_get_called_then_results_delayed(
        self,
    ):
        for query_latency in self.__simulated_latency_subtests():
            pager = self.__create_pager()
            with self.__assert_simulated_latency_applied(query_latency):
                pager.get()

    def test_when_latency_set_to_non_int_value_error_raised(self):
        with self.assertRaises(ValueError) as ex:
            self._manager.initialize({"simulated_query_latency_ms": "A non number value"})

        self.assertEqual(str(ex.exception), "simulated_query_latency_ms must be a number")

    def test_when_latency_set_to_none_value_error_raised(self):
        with self.assertRaises(ValueError) as ex:
            self._manager.initialize({"simulated_query_latency_ms": None})

        self.assertEqual(str(ex.exception), "simulated_query_latency_ms must be a number")

    def test_when_latency_set_to_bool_value_error_raised(self):
        with self.assertRaises(ValueError) as ex:
            self._manager.initialize({"simulated_query_latency_ms": True})

        self.assertEqual(str(ex.exception), "simulated_query_latency_ms must be a number")

    def test_when_latency_set_to_below_zero_value_error_raised(self):
        with self.assertRaises(ValueError) as ex:
            self._manager.initialize({"simulated_query_latency_ms": -1})

        self.assertEqual(str(ex.exception), "simulated_query_latency_ms must not be negative")

    def test_changing_other_settings_does_not_change_latency(self):
        self._manager.initialize({"simulated_query_latency_ms": 50})
        self.assertEqual(self._manager.settings()["simulated_query_latency_ms"], 50)

        valid_library_path = os.path.join(
            os.path.dirname(__file__), "resources", "library_apiComplianceSuite.json"
        )
        self._manager.initialize({"library_path": valid_library_path})
        self.assertEqual(self._manager.settings()["simulated_query_latency_ms"], 50)

    def __create_pager(self):
        """
        Get a pager object wrapping a BALEntityReferencePagerInterface.

        Arbitrarily choose getWithRelationship as a way to get a
        pager - we know it's the same type as returned by
        getWithRelationships.
        """
        entity_ref = self.create_test_entity_references()[0]
        pagers = [None]

        self._manager.getWithRelationship(
            [entity_ref],
            TraitsData(),
            1,
            RelationsAccess.kRead,
            self.createTestContext(),
            lambda idx, pager: operator.setitem(pagers, idx, pager),
            lambda idx, error: self.fail(f"Unexpected BatchElementError {error}"),
        )
        [pager] = pagers

        return pager

    # We wouldn't normally test specific implementation like this, (ie),
    # are we calling a specific function. But because this is time
    # based, this lets us not be vulnerable to specific system timing.
    def __assert_sleep_calls(self, query_latency, patched_time_sleep):
        if query_latency > 0:
            patched_time_sleep.assert_called_once_with(query_latency / 1000.0)
        else:
            patched_time_sleep.assert_not_called()

    def __check_simulated_latencies(self, method, *args, **kwargs):
        for query_latency in self.__simulated_latency_subtests():
            with self.__assert_simulated_latency_applied(query_latency):
                method(*args, mock.Mock(), mock.Mock(), **kwargs)

    def __simulated_latency_subtests(self):
        for query_latency in self.__test_query_latencies:
            with self.subTest(query_latency=query_latency):
                with mock.patch("time.sleep"):  # Patch away delay for setup block.
                    self._manager.initialize({"simulated_query_latency_ms": query_latency})
                    yield query_latency

    @contextlib.contextmanager
    def __assert_simulated_latency_applied(self, query_latency):
        with mock.patch("time.sleep") as patched_time_sleep:
            yield
            self.__assert_sleep_calls(query_latency, patched_time_sleep)
