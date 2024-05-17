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
import posixpath
import string
import pathlib

from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from urllib.parse import urlparse, urlunparse


@dataclass
class EntityInfo:
    """
    Identifies an entity within the BAL library. Convertible to/from
    OpenAssetIO entity references. Used as a key to look up entity data
    or describe a newly created entity.
    """

    name: str
    version: Optional[int]
    access: str


@dataclass
class Entity:
    """
    The data for a specific entity in the library, including traits,
    relations, etc.
    """

    version: int
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
        lib_dir_url = pathlib.Path(lib_dir).as_uri()
    else:
        lib_path = ""
        lib_dir = ""

    # Add our implicit vars on top of any the lib may have defined
    subs_vars = library.setdefault("variables", {})
    subs_vars["bal_library_path"] = lib_path
    subs_vars["bal_library_dir"] = lib_dir
    subs_vars["bal_library_dir_url"] = lib_dir_url

    return library


def exists(entity_info: EntityInfo, library: dict) -> bool:
    """
    Determines if the supplied entity exists in the library
    """
    if entity_info.name not in library["entities"]:
        return False

    version_dict, _ = _entity_version_dict_and_tag(entity_info, library)
    if version_dict is None:
        return False

    return True


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
            entity_infos=[
                EntityInfo(name, version=None, access=entity_info.access)
                for name in relation["entities"]
            ],
        )
        for relation in entity_dict.get("relations", [])
    ]

    version_dict, version_idx = _entity_version_dict_and_tag(entity_info, library)
    if version_dict is None:
        # No version found or explicitly null entry, simulating a failed
        # resolution.
        raise InvalidEntityVersion(entity_info)
    if version_dict.get("traits") is None:
        # Version found but dict empty, simulating an access error.
        raise InaccessibleEntity(entity_info)

    # Expand vars late to allow more flexibility
    expanded_version_dict = _copy_and_expand_trait_properties(version_dict, library)
    return Entity(**expanded_version_dict, relations=relations, version=version_idx)


def management_policy(trait_set: Set[str], access: str, library: dict) -> dict:
    """
    Retrieves the management policy for the supplied trait set. The
    default will be used unless an alternate default or trait set
    specific exception is provided in the library.
    """
    policies = library.get("managementPolicy", {}).get(access, {})
    overrides = policies.get("overrideByTraitSet", [])
    matching_exceptions = (e["policy"] for e in overrides if set(e["traitSet"]) == trait_set)
    policy = next(matching_exceptions, policies.get("default"))

    if policy is None:
        raise LookupError(
            f"BAL library is missing a managementPolicy for '{access}'. Perhaps your library is"
            " missing a 'default'? Please consult the JSON schema."
        )

    return policy


def versions(entity_info: EntityInfo, include_latest: bool, library: dict) -> List[EntityInfo]:
    """
    Retrieves a list of version of the entity, if include_latest is
    true, then an EntityInfo that always retrieves the latest entity
    will be prepended to the list. Entities are returned newest first.
    """
    results = []

    entity_dict = _library_entity_dict(entity_info, library)
    if entity_dict is None:
        raise UnknownBALEntity(entity_info)

    if include_latest:
        results.append(EntityInfo(name=entity_info.name, version=None, access=entity_info.access))

    num_versions = len(entity_dict["versions"])
    for i in range(num_versions, 0, -1):
        results.append(EntityInfo(name=entity_info.name, version=i, access=entity_info.access))

    return results


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
    version_dict, version_tag = _next_entity_version_dict_and_tag(entity_info, library)
    version_dict["traits"] = traits_dict
    entity_info.version = version_tag
    return entity_info


def _entity_version_dict_and_tag(
    entity_info: EntityInfo, library: dict
) -> (Optional[dict], Optional[int]):
    """
    Returns the entity version dict and corresponding tag for the
    specified entity, or None if that version does not exist.
    """
    entity_dict = _ensure_library_entity_dict(entity_info, library)
    versions_list = entity_dict["versions"]

    access_overrides = entity_dict.get("overrideByAccess", {})
    if entity_info.access in access_overrides:
        return access_overrides[entity_info.access], entity_info.version

    if not versions_list:
        return None, None

    if entity_info.version:
        version_index = entity_info.version - 1
        if len(versions_list) <= version_index:
            return None, None
        return versions_list[version_index], entity_info.version

    return versions_list[-1], len(versions_list)


def _next_entity_version_dict_and_tag(entity_info: EntityInfo, library: dict) -> (dict, int):
    """
    Creates and returns a new version entry and its tag for the supplied
    EntityInfo. If this is a new entity, it will be created.
    """
    entity_dict = _ensure_library_entity_dict(entity_info, library)
    version_dict = {"traits": {}}
    entity_dict["versions"].append(version_dict)
    return version_dict, len(entity_dict["versions"])


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

                subbed_val = trait_data[prop]

                if subbed_val.startswith("file:"):
                    trait_data[prop] = normalize_file_url(subbed_val)

    return expanded_dict


def normalize_file_url(maybe_file_url):
    """
    Any string in the library that begins with "file:" will be
    normalized, the main point of this being to collapse upward
    traversals that have been written into the library json.
    """
    # Modified from https://stackoverflow.com/a/4317446

    # Parse the URL into components
    parsed_url = urlparse(maybe_file_url)

    # Resolve upward traversals (`..`).
    normed_path = posixpath.normpath(parsed_url.path)
    if parsed_url.path.endswith("/"):
        normed_path += "/"

    if parsed_url.path == normed_path:
        # No changes were made, so avoid unintended mutations by
        # returning the input unmodified. E.g. `file:123` would get
        # normalised to `file:///123`, which might not be what we want.
        return maybe_file_url

    # Reconstruct the URL, replacing the path component with the
    # normalized path.
    return urlunparse(parsed_url._replace(path=normed_path))


class UnknownBALEntity(RuntimeError):
    """
    An exception raised for a reference to a non-existent entity in the
    library.
    """

    def __init__(self, entity_info: EntityInfo):
        super().__init__(f"Entity '{entity_info.name}' not found")


class InvalidEntityVersion(RuntimeError):
    """
    An exception raised for a reference to a non-existent version of
    an existing entity.
    """

    def __init__(self, entity_info: EntityInfo):
        super().__init__(
            f"Entity '{entity_info.name}' does not have a version {entity_info.version or 1}"
        )


class InaccessibleEntity(RuntimeError):
    """
    An exception raised when an entity is found but is inaccessible.
    """

    def __init__(self, entity_info: EntityInfo):
        super().__init__(f"Entity '{entity_info.name}' is inaccessible for {entity_info.access}")
