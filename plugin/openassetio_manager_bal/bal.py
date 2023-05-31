#
#   Copyright 2013-2022 [The Foundry Visionmongers Ltd]
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
The implementation of the "basic asset library" manager.

See __init__.py for more details on it's high-level approach.

@info This code is a sketch to facilitate testing and sample workflows.
It should never be considered in any way a "good example of how to write
an asset management system". Consequently, it omits a plethora of "good
engineering practice".
"""

import copy
import json
import os
import string

from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from urllib.parse import urlparse

SETTINGS_KEY_LIBRARY_PATH = "library_path"
SETTINGS_KEY_SIMULATED_QUERY_LATENCY = "simulated_query_latency_ms"


@dataclass
class EntityInfo:
    """
    Identifies an entity within the BAL library. Convertible to/from
    OpenAssetIO entity references. Used as a key to look up entity data
    or describe a newly created entity.
    """

    name: str


@dataclass
class Entity:
    """
    The data for a specific entity in the library, including traits,
    relations, etc.
    """

    traits: Dict[str, dict]
    relations: List[dict]


@dataclass
class Relation:
    """
    The definition of a relationship to other entities. The nature of
    the relation is a traits data dict, accompanied by one or more
    EntityInfos.
    """

    traits: Dict[str, Dict]
    entity_infos: List[EntityInfo]


def make_default_settings() -> dict:
    """
    Generates a default settings dict for BAL.
    Note: as a library is required, the default settings are not enough
    to initialize the manager.
    """
    return {SETTINGS_KEY_LIBRARY_PATH: "", SETTINGS_KEY_SIMULATED_QUERY_LATENCY: 10}


def validate_settings(settings: dict):
    """
    Parses the supplied settings dict, raising if there are any
    unrecognized keys present.
    """

    defaults = make_default_settings()

    if SETTINGS_KEY_LIBRARY_PATH in settings:
        if not isinstance(settings[SETTINGS_KEY_LIBRARY_PATH], str):
            raise ValueError(f"{SETTINGS_KEY_LIBRARY_PATH} must be a str")
    if SETTINGS_KEY_SIMULATED_QUERY_LATENCY in settings:
        query_latency = settings[SETTINGS_KEY_SIMULATED_QUERY_LATENCY]
        # This bool check is because bools are also ints as far as
        # python is concerned.
        if isinstance(query_latency, bool) or not isinstance(query_latency, (int, float)):
            raise ValueError(f"{SETTINGS_KEY_SIMULATED_QUERY_LATENCY} must be a number")
        if query_latency < 0:
            raise ValueError(f"{SETTINGS_KEY_SIMULATED_QUERY_LATENCY} must not be negative")

    for key in settings:
        if key not in defaults:
            raise KeyError(f"Unknown setting '{key}'")


def load_library(path: str) -> dict:
    """
    Loads a library from the supplied path
    """
    library = {}

    if path:
        with open(path, "r", encoding="utf-8") as file:
            library.update(json.load(file))
        lib_path = os.path.abspath(path)
        lib_dir = os.path.dirname(lib_path)
    else:
        lib_path = ""
        lib_dir = ""

    # Add our implicit vars on top of any the lib may have defined
    subs_vars = library.setdefault("variables", {})
    subs_vars["bal_library_path"] = lib_path
    subs_vars["bal_library_dir"] = lib_dir

    return library


def parse_entity_ref(entity_ref: str) -> EntityInfo:
    """
    Decomposes an entity reference into bal fields.
    """
    uri_parts = urlparse(entity_ref)

    if len(uri_parts.path) <= 1:
        raise MalformedBALReference("Missing entity name in path component", entity_ref)

    # path will start with a /
    name = uri_parts.path[1:]

    return EntityInfo(name=name)


def exists(entity_info: EntityInfo, library: dict) -> bool:
    """
    Determines if the supplied entity exists in the library
    """
    return entity_info.name in library["entities"]


def entity(entity_info: EntityInfo, library: dict) -> Entity:
    """
    Retrieves the Entity data addressed by the supplied EntityInfo
    """
    entity_dict = _library_entity_dict(entity_info, library)
    if entity_dict is None:
        raise UnknownBALEntity(entity_info)

    relations = [
        Relation(
            traits=relation["traits"],
            entity_infos=[EntityInfo(name) for name in relation["entities"]],
        )
        for relation in entity_dict.get("relations", [])
    ]

    version_dict = entity_dict["versions"][-1]
    # Expand vars late to allow more flexibility
    expanded_version_dict = _copy_and_expand_trait_properties(version_dict, library)
    return Entity(**expanded_version_dict, relations=relations)


def management_policy(trait_set: Set[str], access: str, library: dict) -> dict:
    """
    Retrieves the management policy for the supplied trait set. The
    default will be used unless an alternate default or trait set
    specific exception is provided in the library.
    """
    policies = library.get("managementPolicy", {}).get(access, {})
    exceptions = policies.get("exceptions", [])
    matching_exceptions = (e["policy"] for e in exceptions if set(e["traitSet"]) == trait_set)
    policy = next(matching_exceptions, policies.get("default"))

    if policy is None:
        raise LookupError(
            f"BAL library is missing a managementPolicy for '{access}'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema."
        )

    return policy


def related_references(
    entity_info: EntityInfo,
    requested_relation_traits: dict,
    result_trait_set: Optional[Set[str]],
    library: dict,
) -> List[EntityInfo]:
    """
    Retrieves a list of related entities based on the supplied criteria.
    Relations are un-versioned so will always return an unversioned ref.
    """
    results = []

    # Will throw if invalid
    entity_data = entity(entity_info, library)

    for relation in entity_data.relations:
        # Check if this relation contains the requested traits
        if not _dict_has_traits(relation.traits, requested_relation_traits):
            continue
        for related_entity_info in relation.entity_infos:
            # Check the entity exists, this will throw if not
            relation_data = entity(related_entity_info, library)
            # Check the target entities have the requested traits if needed
            if result_trait_set and not _entity_has_trait_set(relation_data, result_trait_set):
                continue
            results.append(related_entity_info)

    return results


def create_or_update_entity(
    entity_info: EntityInfo, traits_dict: dict, library: dict
) -> EntityInfo:
    """
    Creates a new entity, or updates an existing one to hold the
    supplied traits data.

    Note: This makes no attempt to validate that trait set has not
    changed since the last version. Presently this appends a new
    version to the entity's version list with the updated data.
    """
    version_dict = _next_entity_version_dict(entity_info, library)
    version_dict["traits"] = traits_dict
    # For now, we just keep the same reference until we properly
    # support versioning.
    return entity_info


def _next_entity_version_dict(entity_info: EntityInfo, library: dict) -> dict:
    """
    Creates and returns a new version entry for the supplied EntityInfo.
    If this is a new entity, it will be created.
    """
    entity_dict = _ensure_library_entity_dict(entity_info, library)
    version_dict = {"traits": {}}
    entity_dict["versions"].append(version_dict)
    return version_dict


def _ensure_library_entity_dict(entity_info: EntityInfo, library: dict) -> dict:
    """
    Ensures there is a top-level entity dict for the supplied
    EntityInfo, creating one if required. Newly created entities will
    have no versions.
    """
    entity_dict = library["entities"].setdefault(entity_info.name, {"versions": []})
    return entity_dict


def _library_entity_dict(entity_info: EntityInfo, library: dict):
    """
    Retrieves mutable the library entry for the specified entity.
    """
    entities_dict = library["entities"]
    return entities_dict.get(entity_info.name)


def _dict_has_traits(data: dict, traits: dict) -> bool:
    """
    Determines if the supplied dict-of-dicts contains the given traits.
    A match is when all trait ids are present as top level keys in the
    dict, and any set trait properties exist as child keys with the same
    value. Additional keys at either level in the data dict are ignored.
    """
    for trait_id, trait_data in traits.items():
        if trait_id not in data:
            return False
        for property_key, value in trait_data.items():
            if data[trait_id].get(property_key) != value:
                return False
    return True


def _entity_has_trait_set(entity_data: Entity, trait_set: Set[str]) -> bool:
    """
    Determines if the supplied entity has the requested trait ids within
    its trait set.
    """
    for trait in trait_set:
        if trait not in entity_data.traits:
            return False
    return True


def _copy_and_expand_trait_properties(entity_version_dict: dict, library: dict) -> dict:
    """
    Copies the supplied trait version dict, and expands any variables in
    its trait's string properties. Library variables take precedence
    over an environment variable of the same name.

    Supports $var and ${var}.
    """
    expanded_dict = copy.deepcopy(entity_version_dict)

    for _, trait_data in expanded_dict["traits"].items():
        for prop, value in trait_data.items():
            if isinstance(value, str):
                # On Windows, some iteration methods applied to
                # os.environ miss out keys:
                #
                #   >>> "UserProfile" in os.environ
                #   True
                #   >>> "UserProfile" in os.environ.keys()
                #   True
                #   >>> "UserProfile" in os.environ.copy()
                #   False
                #   >>> "UserProfile" in set(os.environ.keys())
                #   False
                #
                # As such, we need to use the original object, and
                # append the other vars as kwarg. Fortunately this has
                # exactly the precedence behaviour we want.
                trait_data[prop] = string.Template(value).safe_substitute(
                    os.environ, **library["variables"]
                )

    return expanded_dict


class UnknownBALEntity(RuntimeError):
    """
    An exception raised for a reference to a non-existent entity in the
    library.
    """

    def __init__(self, entity_info: EntityInfo):
        super().__init__(f"Entity '{entity_info.name}' not found")


class MalformedBALReference(RuntimeError):
    """
    An exception raised for a reference that is missing an entity name
    or other required part.
    """

    def __init__(self, message, reference: str):
        super().__init__(f"Malformed BAL reference: {message} '{reference}'")
