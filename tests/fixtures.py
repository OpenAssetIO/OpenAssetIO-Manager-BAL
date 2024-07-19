#
#   Copyright 2013-2022 The Foundry Visionmongers Ltd
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
Manager test harness fixtures for the apiComplianceSuite
"""

import json
import os

from openassetio import constants
from openassetio.trait import TraitsData
from openassetio_mediacreation.traits.lifecycle import VersionTrait


#
# Test library
#

test_library_path = os.path.join(
    os.path.dirname(__file__), "resources", "library_apiComplianceSuite.json"
)
blank_library_path = os.path.join(os.path.dirname(__file__), "resources", "library_empty.json")
test_libray = {}

with open(test_library_path, "r", encoding="utf-8") as file:
    test_library = json.load(file)

#
# Constants
#

IDENTIFIER = "org.openassetio.examples.manager.bal"

VALID_REF = "bal:///references/can/contain/🐠"
NON_REF = "not a Ŕeference"
MALFORMED_REF = "bal:///"
ERROR_MSG_MALFORMED_REF = "Missing entity name in path component (bal:///)"
MISSING_REF = "bal:///missing_entity"
ERROR_MSG_MISSING_ENTITY = "Entity 'missing_entity' not found"

an_existing_entity_name, another_existing_entity_name = tuple(test_library["entities"].keys())[0:2]
an_existing_entity_trait_set = set(
    test_library["entities"][an_existing_entity_name]["versions"][-1]["traits"].keys()
)
another_existing_entity_trait_set = set(
    test_library["entities"][another_existing_entity_name]["versions"][-1]["traits"].keys()
)

some_registerable_traitset = {"trait1", "trait2"}
some_registerable_traitsdata = TraitsData()
some_registerable_traitsdata.setTraitProperty("trait1", "some", "stringValue")
some_registerable_traitsdata.setTraitProperty("trait2", "count", 4)

RELATEABLE_REF = "bal:///entity/original"
known_relationship_traitset = {"proxy"}
known_relationship_traitset_related_references = [
    "bal:///entity/proxy/1",
    "bal:///entity/proxy/2",
    "bal:///entity/proxy/3",
]
known_relationship_traitsdata = TraitsData(known_relationship_traitset)
known_relationship_traitsdata.setTraitProperty("proxy", "type", "alt")
known_relationship_traitsdata_related_references = [
    "bal:///entity/proxy/3",
]
known_relationship_result_traitset = {"b"}
known_relationship_result_traitset_related_references = [
    "bal:///entity/proxy/2",
    "bal:///entity/proxy/3",
]

fixtures = {
    "identifier": IDENTIFIER,
    "settings": {"library_path": test_library_path, "simulated_query_latency_ms": 1},
    "shared": {
        "a_valid_reference": VALID_REF,
        "an_invalid_reference": NON_REF,
        "a_malformed_reference": MALFORMED_REF,
    },
    "Test_identifier": {"test_matches_fixture": {"identifier": IDENTIFIER}},
    "Test_displayName": {"test_matches_fixture": {"display_name": "Basic Asset Library 📖"}},
    "Test_info": {
        "test_matches_fixture": {
            "info": {constants.kInfoKey_EntityReferencesMatchPrefix: "bal:///"}
        }
    },
    "Test_initialize": {
        "test_when_settings_have_all_keys_then_all_settings_updated": {
            "some_settings_with_all_keys": {
                "library_path": blank_library_path,
                "simulated_query_latency_ms": 0,
                "entity_reference_url_scheme": "thingy",
            }
        },
        "test_when_settings_have_subset_of_keys_then_other_settings_unchanged": {
            "some_settings_with_a_subset_of_keys": {"simulated_query_latency_ms": 2}
        },
        "test_when_subset_of_settings_modified_then_other_settings_unchanged": {
            "some_settings_with_a_subset_of_keys": {"simulated_query_latency_ms": 2}
        },
    },
    "Test_entityExists": {
        "shared": {
            "a_reference_to_an_existing_entity": f"bal:///{an_existing_entity_name}",
        },
        "test_when_querying_existing_reference_then_true_is_returned": {},
        "test_when_querying_nonexisting_reference_then_false_is_returned": {
            "a_reference_to_a_nonexisting_entity": VALID_REF
        },
        "test_when_querying_existing_and_nonexisting_references_then_true_and_false_is_returned": {
            "a_reference_to_a_nonexisting_entity": VALID_REF,
        },
        "test_when_querying_malformed_reference_then_malformed_reference_error_is_returned": {
            "a_malformed_reference": MALFORMED_REF,
            "expected_error_message": ERROR_MSG_MALFORMED_REF,
        },
    },
    "Test_entityTraits": {
        "test_when_querying_malformed_reference_then_malformed_reference_error_is_returned": {
            "a_malformed_reference": MALFORMED_REF,
            "expected_error_message": ERROR_MSG_MALFORMED_REF,
        },
        "test_when_querying_missing_reference_for_read_then_resolution_error_is_returned": {
            "a_reference_to_a_missing_entity": MISSING_REF,
            "expected_error_message": ERROR_MSG_MISSING_ENTITY,
        },
        "test_when_read_only_entity_queried_for_write_then_access_error_is_returned": {
            # No such thing as a read-only entity in BAL - skip for now.
            # "a_reference_to_a_readonly_entity": ...
        },
        "test_when_write_only_entity_queried_for_read_then_access_error_is_returned": {
            # Missing entities are write-only, but they have a different
            # error behaviour, so can't be used here.
            # "a_reference_to_a_writeonly_entity": ...
        },
        "test_when_multiple_references_for_read_then_same_number_of_returned_trait_sets": {
            "first_entity_reference": f"bal:///{an_existing_entity_name}",
            "first_entity_trait_set": an_existing_entity_trait_set | {VersionTrait.kId},
            "second_entity_reference": f"bal:///{another_existing_entity_name}",
            "second_entity_trait_set": another_existing_entity_trait_set | {VersionTrait.kId},
        },
        "test_when_multiple_references_for_write_then_same_number_of_returned_trait_sets": {
            "first_entity_reference": f"bal:///{an_existing_entity_name}",
            "first_entity_trait_set": an_existing_entity_trait_set,
            "second_entity_reference": f"bal:///{another_existing_entity_name}",
            "second_entity_trait_set": another_existing_entity_trait_set,
        },
    },
    "Test_resolve": {
        "shared": {
            "a_reference_to_a_readable_entity": f"bal:///{an_existing_entity_name}",
            "a_set_of_valid_traits": {"string", "number"},
            "a_reference_to_a_readonly_entity": "bal:///a read only asset",
            "the_error_string_for_a_reference_to_a_readonly_entity": (
                "Entity 'a read only asset' is inaccessible for managerDriven"
            ),
            "a_reference_to_a_missing_entity": MISSING_REF,
            "the_error_string_for_a_reference_to_a_missing_entity": ERROR_MSG_MISSING_ENTITY,
            "a_malformed_reference": MALFORMED_REF,
            "the_error_string_for_a_malformed_reference": ERROR_MSG_MALFORMED_REF,
        }
    },
    "Test_preflight": {
        "test_when_multiple_references_then_same_number_of_returned_references": {
            "a_traits_data_for_preflight": TraitsData({"anything"}),
            "a_reference_for_preflight": "bal:///someNewEntity",
        },
        "test_when_reference_is_read_only_then_access_error_is_returned": {
            # Skipped: all BAL entities can be published to.
            # "a_traits_data_for_preflight":
            # "a_reference_to_a_readonly_entity":,
            # "expected_error_message":
        },
        "test_when_reference_malformed_then_malformed_entity_reference_error_returned": {
            "a_traits_data_for_preflight": TraitsData({"anything"}),
            "a_malformed_reference": MALFORMED_REF,
            "expected_error_message": ERROR_MSG_MALFORMED_REF,
        },
        "test_when_preflight_hint_invalid_then_invalid_preflight_hint_error_returned": {
            # Skipped: all BAL entities can be published to.
            # "an_invalid_traits_data_for_preflight":
            # "a_reference_for_preflight":,
            # "expected_error_message":
        },
    },
    "Test_register": {
        "shared": {
            "a_reference_to_a_writable_entity": "bal:///someNewEntity",
            "a_traitsdata_for_a_reference_to_a_writable_entity": some_registerable_traitsdata,
            "the_error_string_for_a_malformed_reference": ERROR_MSG_MALFORMED_REF,
        }
    },
    "Test_getWithRelationship_All": {
        "test_when_relation_unknown_then_no_pages_returned": {"a_reference": RELATEABLE_REF},
        "test_when_multiple_relationship_types_then_same_number_of_returned_relationships": {
            "a_reference": RELATEABLE_REF,
            "a_relationship_trait_set": known_relationship_traitset,
        },
        "test_when_batched_then_same_number_of_returned_relationships": {
            "a_reference": RELATEABLE_REF,
            "a_relationship_trait_set": known_relationship_traitset,
        },
        "test_when_relationship_trait_set_known_then_all_with_trait_set_returned": {
            "a_reference": RELATEABLE_REF,
            "a_relationship_trait_set": known_relationship_traitset,
            "expected_related_entity_references": known_relationship_traitset_related_references,
        },
        "test_when_relationship_trait_set_known_and_props_set_then_filtered_refs_returned": {
            "a_reference": RELATEABLE_REF,
            "a_relationship_traits_data_with_props": known_relationship_traitsdata,
            "expected_related_entity_references": known_relationship_traitsdata_related_references,
        },
        "test_when_result_trait_set_supplied_then_filtered_refs_returned": {
            "a_reference": RELATEABLE_REF,
            "a_relationship_trait_set": known_relationship_traitset,
            "an_entity_trait_set_to_filter_by": known_relationship_result_traitset,
            "expected_related_entity_references": (
                known_relationship_result_traitset_related_references
            ),
        },
        "test_when_querying_missing_reference_then_resolution_error_is_returned": {
            "a_reference_to_a_missing_entity": MISSING_REF,
            "a_relationship_trait_set": known_relationship_traitset,
            "expected_error_message": ERROR_MSG_MISSING_ENTITY,
        },
        "test_when_querying_malformed_reference_then_malformed_reference_error_is_returned": {
            "a_malformed_reference": MALFORMED_REF,
            "a_relationship_trait_set": known_relationship_traitset,
            "expected_error_message": ERROR_MSG_MALFORMED_REF,
        },
        "test_when_related_entities_span_multiple_pages_then_pager_has_multiple_pages": {
            "a_reference": RELATEABLE_REF,
            "a_relationship_trait_set": known_relationship_traitset,
            "expected_related_entity_references": known_relationship_traitset_related_references,
        },
        "test_when_pager_constructed_then_no_references_to_original_args_are_retained": {
            "a_reference": RELATEABLE_REF,
            "a_relationship_trait_set": known_relationship_traitset,
            "an_entity_trait_set_to_filter_by": known_relationship_result_traitset,
        },
    },
}
