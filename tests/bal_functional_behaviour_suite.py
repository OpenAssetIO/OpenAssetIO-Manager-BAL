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

# pylint: disable=invalid-name, missing-function-docstring, missing-class-docstring

import os
from unittest import mock

from openassetio import Context, TraitsData
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
        self.__check_simulated_latencies_with_callbacks(
            self._manager.resolve,
            self.create_test_entity_references(),
            {"string"},
            self.createTestContext(access=Context.Access.kRead),
        )

    def test_when_preflight_called_then_results_delayed_by_specified_simulated_query_latency(self):
        self.__check_simulated_latencies_with_callbacks(
            self._manager.preflight,
            self.create_test_entity_references(),
            {"string"},
            self.createTestContext(access=Context.Access.kRead),
        )

    def test_when_entityExists_called_then_results_delayed_by_specified_simulated_query_latency(
        self,
    ):
        self.__check_simulated_latencies_without_callbacks(
            self._manager.entityExists,
            self.create_test_entity_references(),
            self.createTestContext(access=Context.Access.kRead),
        )

    def test_when_register_called_then_results_delayed_by_specified_simulated_query_latency(self):
        entity_refs = self.create_test_entity_references()
        traits_datas = [TraitsData() for _ in entity_refs]

        self.__check_simulated_latencies_with_callbacks(
            self._manager.register,
            entity_refs,
            traits_datas,
            self.createTestContext(access=Context.Access.kRead),
        )

    def test_when_getWithRelationship_called_then_results_delayed_by_specified_query_latency(
        self,
    ):
        entity_refs = self.create_test_entity_references()

        self.__check_simulated_latencies_without_callbacks(
            self._manager.getWithRelationship,
            TraitsData(),
            entity_refs,
            self.createTestContext(access=Context.Access.kRead),
        )

    def test_when_getWithRelationships_called_then_results_delayed_by_specified_query_latency(
        self,
    ):
        entity_ref = self.create_test_entity_references()[0]
        traits_datas = [TraitsData()] * 3

        self.__check_simulated_latencies_without_callbacks(
            self._manager.getWithRelationships,
            traits_datas,
            entity_ref,
            self.createTestContext(access=Context.Access.kRead),
        )

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

    # We wouldn't normally test specific implementation like this, (ie),
    # are we calling a specific function. But because this is time
    # based, this lets us not be vulnerable to specific system timing.
    def __assert_sleep_calls(self, query_latency, patched_time_sleep):
        if query_latency > 0:
            patched_time_sleep.assert_called_once_with(query_latency / 1000.0)
        else:
            patched_time_sleep.assert_not_called()

    def __check_simulated_latencies_with_callbacks(self, method, *args, **kwargs):
        def assert_cb(idx, traits_data):
            self.__assert_sleep_calls(query_latency, patched_time_sleep)

        for query_latency in self.__test_query_latencies:
            with self.subTest(query_latency=query_latency):
                self._manager.initialize({"simulated_query_latency_ms": query_latency})
                with mock.patch("time.sleep", return_value=None) as patched_time_sleep:
                    # Call assert in the callback to guarantee than by
                    # the time the callback is invoked, sleep has
                    # already been called.

                    method(*args, assert_cb, assert_cb, **kwargs)

    def __check_simulated_latencies_without_callbacks(self, method, *args, **kwargs):
        for query_latency in self.__test_query_latencies:
            with self.subTest(query_latency=query_latency):
                self._manager.initialize({"simulated_query_latency_ms": query_latency})
                with mock.patch("time.sleep", return_value=None) as patched_time_sleep:
                    method(*args, **kwargs)
                    self.__assert_sleep_calls(query_latency, patched_time_sleep)
