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

from openassetio import TraitsData
from openassetio.constants import kField_EntityReferencesMatchPrefix

#
# Test library
#

test_library_path = os.path.join(
    os.path.dirname(__file__), "resources", "library_apiComplianceSuite.json"
)
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

an_existing_entity_name = next(iter(test_library["entities"].keys()))

some_registerable_traitset = {"trait1", "trait2"}
some_registerable_traitsdata = TraitsData()
some_registerable_traitsdata.setTraitProperty("trait1", "some", "stringValue")
some_registerable_traitsdata.setTraitProperty("trait2", "count", 4)

fixtures = {
    "identifier": IDENTIFIER,
    "settings": {"library_path": test_library_path},
    "shared": {
        "a_valid_reference": VALID_REF,
        "an_invalid_reference": NON_REF,
        "a_malformed_reference": MALFORMED_REF,
    },
    "Test_identifier": {"test_matches_fixture": {"identifier": IDENTIFIER}},
    "Test_displayName": {"test_matches_fixture": {"display_name": "Basic Asset Library 📖"}},
    "Test_info": {
        "test_matches_fixture": {"info": {kField_EntityReferencesMatchPrefix: "bal:///"}}
    },
    "Test_initialize": {
        "shared": {
            "some_settings_with_new_values_and_invalid_keys": {"library_path": "", "cat": True}
        },
        "test_when_settings_expanded_then_manager_settings_updated": {
            "some_settings_with_all_keys": {"library_path": ""}
        },
        "test_when_subset_of_settings_modified_then_other_settings_unchanged": {
            "some_settings_with_a_subset_of_keys": {}
        },
    },
    "Test_entityExists": {
        "shared": {
            "a_reference_to_an_existing_entity": f"bal:///{an_existing_entity_name}",
            "a_reference_to_a_nonexisting_entity": VALID_REF,
        }
    },
    "Test_resolve": {
        "shared": {
            "a_reference_to_a_readable_entity": f"bal:///{an_existing_entity_name}",
            "a_set_of_valid_traits": {"string", "number"},
            "a_reference_to_a_readonly_entity": f"bal:///{an_existing_entity_name}",
            "the_error_string_for_a_reference_to_a_readonly_entity": "BAL entities are read-only",
            "a_reference_to_a_missing_entity": "bal:///missing_entity",
            "the_error_string_for_a_reference_to_a_missing_entity": (
                "Entity 'bal:///missing_entity' not found"
            ),
            "a_malformed_reference": MALFORMED_REF,
            "the_error_string_for_a_malformed_reference": (
                "Missing entity name in path component"
            ),
        }
    },
    "Test_preflight": {
        "shared": {
            "a_reference_to_a_writable_entity": "bal:///someNewEntity",
            "a_set_of_valid_traits": some_registerable_traitset,
            "the_error_string_for_a_malformed_reference": (
                "Missing entity name in path component"
            ),
        }
    },
    "Test_register": {
        "shared": {
            "a_reference_to_a_writable_entity": "bal:///someNewEntity",
            "a_traitsdata_for_a_reference_to_a_writable_entity": some_registerable_traitsdata,
            "the_error_string_for_a_malformed_reference": (
                "Missing entity name in path component"
            ),
        }
    },
}
