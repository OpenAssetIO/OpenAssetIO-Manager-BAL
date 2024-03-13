#
#   Copyright 2013-2023 [The Foundry Visionmongers Ltd]
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

# Fix module-level name check, as well as OpenAssetIO methods
# pylint: disable=invalid-name
"""
A single-class module, providing the BasicAssetLibraryInterface class.
"""
import os
import re
import time

from functools import wraps
from typing import Iterable, List, Any
from urllib.parse import urlparse, parse_qs

from openassetio import constants, EntityReference
from openassetio.access import (
    ResolveAccess,
    EntityTraitsAccess,
    PublishingAccess,
    RelationsAccess,
    kAccessNames,
)
from openassetio.errors import BatchElementError, ConfigurationException
from openassetio.managerApi import ManagerInterface, EntityReferencePagerInterface
from openassetio.trait import TraitsData

from openassetio_mediacreation.traits.lifecycle import VersionTrait, StableTrait
from openassetio_mediacreation.specifications.lifecycle import (
    EntityVersionsRelationshipSpecification,
    StableEntityVersionsRelationshipSpecification,
    StableReferenceRelationshipSpecification,
)

from . import bal


__all__ = [
    "BasicAssetLibraryInterface",
]

SETTINGS_KEY_LIBRARY_PATH = "library_path"
SETTINGS_KEY_SIMULATED_QUERY_LATENCY = "simulated_query_latency_ms"
SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME = "entity_reference_url_scheme"

VERSION_TAG_LATEST = "latest"


# TODO(TC): @pylint-disable
# As we are building out the implementation vertically, we have known
# fails for missing abstract methods.
# pylint: disable=abstract-method
# Methods in C++ end up with "missing docstring"
# pylint: disable=missing-docstring
# pylint: disable=too-many-arguments, unused-argument


def simulated_delay(func):
    @wraps(func)
    def wrapper_simulated_delay(self, *args, **kwargs):
        # pylint: disable=protected-access
        delay_ms = self.simulated_latency
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)  # sleep takes seconds
        return func(self, *args, **kwargs)

    return wrapper_simulated_delay


class MalformedEntityReference(RuntimeError):
    """
    An exception raised for a reference to an entity reference that is
    formatted incorrectly or otherwise malformed.
    """

    def __init__(self, malformed_reason: str, entity_ref: str):
        super().__init__(f"{malformed_reason} ({entity_ref})")


class BasicAssetLibraryInterface(ManagerInterface):
    """
    This class exposes the Basic Asset Library through the OpenAssetIO
    ManagerInterface.
    """

    __lib_path_envvar_name = "BAL_LIBRARY_PATH"

    def __init__(self):
        super().__init__()
        self.__settings = self.__make_default_settings()
        self.__library = {}

    def identifier(self):
        return "org.openassetio.examples.manager.bal"

    def displayName(self):
        # Deliberately includes unicode chars to test string handling
        return "Basic Asset Library 📖"

    def info(self):
        return {constants.kInfoKey_EntityReferencesMatchPrefix: self.__entity_refrence_prefix()}

    def settings(self, hostSession):
        return self.__settings.copy()

    def hasCapability(self, capability):
        if capability in (
            ManagerInterface.Capability.kEntityReferenceIdentification,
            ManagerInterface.Capability.kManagementPolicyQueries,
            ManagerInterface.Capability.kEntityTraitIntrospection,
            ManagerInterface.Capability.kResolution,
            ManagerInterface.Capability.kPublishing,
            ManagerInterface.Capability.kRelationshipQueries,
            ManagerInterface.Capability.kExistenceQueries,
        ):
            return True

        return False

    @property
    def simulated_latency(self):
        """
        BAL internal convenience to get the simulated latency of API
        methods.

        This is read-only - updating the latency must be done via the
        settings mechanism, i.e. re-`initialize` the plugin.
        """
        return self.__settings.get(SETTINGS_KEY_SIMULATED_QUERY_LATENCY, 0)

    def initialize(self, managerSettings, hostSession):
        self.__validate_settings(managerSettings)

        # Settings updates can be partial, so make sure we keep any
        # existing path.
        existing_library_path = self.__settings.get("library_path")
        library_path = managerSettings.get("library_path", existing_library_path)

        if not library_path:
            hostSession.logger().log(
                hostSession.logger().Severity.kDebug,
                "'library_path' not in settings or is empty, checking "
                f"{self.__lib_path_envvar_name}",
            )
            library_path = os.environ.get(self.__lib_path_envvar_name)

        if not library_path:
            raise ConfigurationException(
                f"'library_path'/{self.__lib_path_envvar_name} not set or is empty"
            )

        self.__settings.update(managerSettings)
        self.__settings["library_path"] = library_path

        self.__library = {}
        hostSession.logger().log(
            hostSession.logger().Severity.kDebug,
            f"Loading library from '{library_path}'",
        )
        self.__library = bal.load_library(library_path)

        hostSession.logger().log(
            hostSession.logger().Severity.kDebug,
            f"Running with simulated query latency of "
            f"{self.__settings[SETTINGS_KEY_SIMULATED_QUERY_LATENCY]}ms",
        )

    def managementPolicy(self, traitSets, access, context, hostSession):
        ## NOTE:
        #
        # BAL _should_ really explicitly handle the versioning related
        # traits here. However, whilst BAL is in limbo between being a
        # mock and a 'functional' manager, then we leave this up to the
        # json configuration, so a host can simulate a manager both
        # with, and without versioning support. If BAL wasn't soon to be
        # re-written, adding a setting may make more sense.
        #
        # When queried for read, a well-behaved implementation here
        # would:
        #
        #  - Imbue the ManagedTrait for the relation trait
        #    sets EntityVersionsRelationshipSpecification and
        #    StableEntityVersionsRelationshipSpecification, to note that
        #    they can be used with getWithRelationship.
        #
        #  - Imbue the VersionTrait if requested in an entity trait
        #    set to indicate it can be resolved.

        return [
            self.__dict_to_traits_data(
                bal.management_policy(trait_set, kAccessNames[int(access)], self.__library)
            )
            for trait_set in traitSets
        ]

    def isEntityReferenceString(self, someString, hostSession):
        return someString.startswith(self.__entity_refrence_prefix())

    @simulated_delay
    def entityExists(self, entityRefs, context, _hostSession, successCallback, errorCallback):
        for idx, ref in enumerate(entityRefs):
            try:
                # Use resolve-for-read access mode as closest analog.
                entity_info = self.__parse_entity_ref(ref.toString(), ResolveAccess.kRead)
                result = bal.exists(entity_info, self.__library)
                successCallback(idx, result)
            except Exception as exc:  # pylint: disable=broad-except
                self.__handle_exception(exc, idx, errorCallback)

    @simulated_delay
    def entityTraits(
        self, entityRefs, entityTraitsAccess, context, _hostSession, successCallback, errorCallback
    ):
        for idx, ref in enumerate(entityRefs):
            try:
                entity_info = self.__parse_entity_ref(ref.toString(), entityTraitsAccess)

                if entityTraitsAccess == EntityTraitsAccess.kRead:
                    entity = bal.entity(entity_info, self.__library)
                    result = set(entity.traits.keys())
                    # VersionTrait for read, but not for write.
                    result |= {VersionTrait.kId}
                else:  # entityTraitsAccess == EntityTraitsAccess.kWrite
                    if bal.exists(entity_info, self.__library):
                        entity = bal.entity(entity_info, self.__library)
                        result = set(entity.traits.keys())
                    else:
                        # Non-existent entities are writable with no
                        # trait restrictions.
                        result = set()

                successCallback(idx, result)
            except Exception as exc:  # pylint: disable=broad-except
                self.__handle_exception(exc, idx, errorCallback)

    @simulated_delay
    def resolve(
        self,
        entityReferences,
        traitSet,
        access,
        context,
        hostSession,
        successCallback,
        errorCallback,
    ):
        # pylint: disable=too-many-locals
        for idx, ref in enumerate(entityReferences):
            try:
                entity_info = self.__parse_entity_ref(ref.toString(), access)
                entity = bal.entity(entity_info, self.__library)

                # Ensure this entity supports the type of access
                # requested.
                result = TraitsData()
                for trait in traitSet:
                    trait_data = entity.traits.get(trait)
                    if trait_data:
                        self.__add_trait_to_traits_data(trait, trait_data, result)

                if VersionTrait.kId in traitSet:
                    version_trait = VersionTrait(result)
                    version_trait.setStableTag(str(entity.version))
                    version_trait.setSpecifiedTag(str(entity_info.version or VERSION_TAG_LATEST))

                successCallback(idx, result)
            except Exception as exc:  # pylint: disable=broad-except
                self.__handle_exception(exc, idx, errorCallback)

    @simulated_delay
    def preflight(
        self,
        targetEntityRefs,
        traitsDatas,
        access,
        context,
        hostSession,
        successCallback,
        errorCallback,
    ):
        if not self.__validate_access(
            "preflight",
            (PublishingAccess.kWrite,),
            access,
            targetEntityRefs,
            errorCallback,
        ):
            return

        for idx, ref in enumerate(targetEntityRefs):
            if not self.__validate_publish_policy(traitsDatas[idx], access, idx, errorCallback):
                continue
            try:
                entity_info = self.__parse_entity_ref(ref.toString(), access)

                if not self.__validate_publish_entity_traits(
                    entity_info, traitsDatas[idx].traitSet(), idx, errorCallback
                ):
                    continue
                # Remove version info from the reference, as publishing will
                # will always create a new version.
                # TODO(tc): Create a placeholder version
                entity_info.version = None
                successCallback(idx, self.__build_entity_ref(entity_info))
            except Exception as exc:  # pylint: disable=broad-except
                self.__handle_exception(exc, idx, errorCallback)

    @simulated_delay
    def register(
        self,
        targetEntityRefs,
        entityTraitsDatas,
        access,
        context,
        hostSession,
        successCallback,
        errorCallback,
    ):
        if not self.__validate_access(
            "register",
            (PublishingAccess.kWrite,),
            access,
            targetEntityRefs,
            errorCallback,
        ):
            return

        for idx, ref in enumerate(targetEntityRefs):
            if not self.__validate_publish_policy(
                entityTraitsDatas[idx], access, idx, errorCallback
            ):
                continue

            try:
                entity_info = self.__parse_entity_ref(ref.toString(), access)

                if not self.__validate_publish_entity_traits(
                    entity_info, entityTraitsDatas[idx].traitSet(), idx, errorCallback
                ):
                    continue

                traits_dict = self.__traits_data_to_dict(entityTraitsDatas[idx])
                updated_entity_info = bal.create_or_update_entity(
                    entity_info, traits_dict, self.__library
                )
                successCallback(idx, self.__build_entity_ref(updated_entity_info))
            except Exception as exc:  # pylint: disable=broad-except
                self.__handle_exception(exc, idx, errorCallback)

    def __validate_publish_entity_traits(self, entity_info, trait_ids, idx, error_callback):
        if not bal.exists(entity_info, self.__library):
            # Can publish with any traits if the entity doesn't exist.
            return True

        entity = bal.entity(entity_info, self.__library)
        # Entities must be published with the same trait set as they
        # currently have (can be overridden per access mode).
        if not set(entity.traits.keys()).issubset(trait_ids):
            error_callback(
                idx,
                BatchElementError(
                    BatchElementError.ErrorCode.kInvalidTraitSet,
                    "Publishing to this entity requires traits that are missing from the input",
                ),
            )
            return False
        return True

    def __validate_publish_policy(self, traits_data, access, idx, error_callback):
        policy = bal.management_policy(
            traits_data.traitSet(), kAccessNames[access], self.__library
        )
        if not policy:
            error_callback(
                idx,
                BatchElementError(
                    BatchElementError.ErrorCode.kInvalidTraitSet,
                    "Publishing is not supported for the given trait set",
                ),
            )
            return False
        return True

    @simulated_delay
    def getWithRelationship(
        self,
        entityReferences,
        relationshipTraitsData,
        resultTraitSet,
        pageSize,
        access,
        context,
        _hostSession,
        successCallback,
        errorCallback,
    ):
        if not self.__validate_access(
            "relationship query",
            (RelationsAccess.kRead,),
            access,
            entityReferences,
            errorCallback,
        ):
            return
        for idx, entity_ref in enumerate(entityReferences):
            try:
                entity_info = self.__parse_entity_ref(entity_ref.toString(), access)
                relations = self.__get_relations(
                    entity_info, relationshipTraitsData, resultTraitSet
                )
                successCallback(
                    idx,
                    BALEntityReferencePagerInterface(
                        self.simulated_latency,
                        pageSize,
                        [self.__build_entity_ref(info) for info in relations],
                    ),
                )
            except Exception as exc:  # pylint: disable=broad-except
                self.__handle_exception(exc, idx, errorCallback)

    @simulated_delay
    def getWithRelationships(
        self,
        entityReference,
        relationshipTraitsDatas,
        resultTraitSet,
        pageSize,
        access,
        context,
        _hostSession,
        successCallback,
        errorCallback,
    ):
        if not self.__validate_access(
            "relationship query",
            (RelationsAccess.kRead,),
            access,
            relationshipTraitsDatas,
            errorCallback,
        ):
            return
        for idx, relationship in enumerate(relationshipTraitsDatas):
            try:
                entity_info = self.__parse_entity_ref(entityReference.toString(), access)
                relations = self.__get_relations(entity_info, relationship, resultTraitSet)
                successCallback(
                    idx,
                    BALEntityReferencePagerInterface(
                        self.simulated_latency,
                        pageSize,
                        [self.__build_entity_ref(info) for info in relations],
                    ),
                )
            except Exception as exc:  # pylint: disable=broad-except
                self.__handle_exception(exc, idx, errorCallback)

    def __get_relations(self, entity_info, relationship_traits_data, result_trait_set):
        """
        Retrieves relations based on the supplied traits data, by
        dispatching to individual handlers for any implicit relationship
        specifications. Falling back on library defined relations in all
        other cases.
        """
        relationship_trait_set = relationship_traits_data.traitSet()

        # We don't use issuperset as otherwise we'd end up responding to
        # any more specialized relationship definitions that may be
        # added in the future, with incorrect results.

        if relationship_trait_set in (
            EntityVersionsRelationshipSpecification.kTraitSet,
            StableEntityVersionsRelationshipSpecification.kTraitSet,
        ):
            # Fetch other versions of the same entity
            return self.__get_relations_entity_versions(entity_info, relationship_traits_data)

        if relationship_trait_set == StableReferenceRelationshipSpecification.kTraitSet:
            # Remove dynamic behaviour from the reference
            return self.__get_relation_stable(entity_info)

        return self.__get_relations_from_library(
            entity_info, relationship_traits_data, result_trait_set
        )

    def __get_relations_entity_versions(self, entity_info, relationship_traits_data):
        """
        Retrieves entity infos for versions of the specified entity.
        """
        include_latest = StableTrait.kId not in relationship_traits_data.traitSet()
        versions = bal.versions(entity_info, include_latest, self.__library)
        # Filter to a specific version if requested
        specified_version = VersionTrait(relationship_traits_data).getSpecifiedTag()
        if specified_version:
            if specified_version == VERSION_TAG_LATEST:
                versions = [versions[0]]
            else:
                versions = [i for i in versions if i.version == int(specified_version)]

        return versions

    def __get_relation_stable(self, entity_info):
        """
        Provides a single stable entity_info devoid of any dynamic
        behaviour.
        """
        # If we have no version, fetch the latest EntityInfo
        # with a stable version defined, otherwise, the input
        # EntityInfo is already stable (for now).
        if entity_info.version is None:
            versions = bal.versions(entity_info, include_latest=False, library=self.__library)
            entity_info = versions[0]
        return [
            entity_info,
        ]

    def __get_relations_from_library(
        self, entity_info, relationship_traits_data, result_trait_set
    ):
        """
        Retrieves arbitrary relations as defined in the BAL library.
        """
        return bal.related_references(
            entity_info,
            self.__traits_data_to_dict(relationship_traits_data),
            result_trait_set,
            self.__library,
        )

    @classmethod
    def __parse_entity_ref(cls, entity_ref: str, access) -> bal.EntityInfo:
        """
        Decomposes an entity reference into bal fields.
        """
        uri_parts = urlparse(entity_ref)

        if len(uri_parts.path) <= 1:
            raise MalformedEntityReference("Missing entity name in path component", entity_ref)

        # path will start with a /
        name = uri_parts.path[1:]

        version = None

        if uri_parts.query:
            params = parse_qs(uri_parts.query)
            version = cls.__version_from_query_params(params, entity_ref)

        return bal.EntityInfo(name=name, version=version, access=kAccessNames[access])

    @staticmethod
    def __version_from_query_params(query_params, entity_ref) -> int:
        """
        Determine the version based on the presence of 'v' in the
        supplied query params.
        """
        if "v" not in query_params:
            return None

        v_str = query_params["v"][-1]
        if v_str == VERSION_TAG_LATEST:
            return None

        try:
            v = int(v_str)
        except ValueError as exc:
            raise MalformedEntityReference(
                f"Version query parameter 'v' must be an int or '{VERSION_TAG_LATEST}'", entity_ref
            ) from exc
        if v < 1:
            raise MalformedEntityReference(
                "Version query parameter 'v' must be greater than 1", entity_ref
            )

        return v

    def __build_entity_ref(self, entity_info: bal.EntityInfo) -> EntityReference:
        """
        Builds an openassetio EntityReference from a BAL EntityInfo
        """
        ref_string = f"{self.__entity_refrence_prefix()}{entity_info.name}"
        if entity_info.version:
            ref_string += f"?v={entity_info.version}"
        return self._createEntityReference(ref_string)

    def __entity_refrence_prefix(self):
        return f"{self.__settings[SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME]}:///"

    @classmethod
    def __dict_to_traits_data(cls, traits_dict: dict):
        traits_data = TraitsData()
        for trait_id, trait_properties in traits_dict.items():
            cls.__add_trait_to_traits_data(trait_id, trait_properties, traits_data)
        return traits_data

    @classmethod
    def __traits_data_to_dict(cls, traits_data: TraitsData):
        return {
            trait_id: {
                prop_key: traits_data.getTraitProperty(trait_id, prop_key)
                for prop_key in traits_data.traitPropertyKeys(trait_id)
            }
            for trait_id in traits_data.traitSet()
        }

    @staticmethod
    def __add_trait_to_traits_data(trait_id: str, trait_properties: dict, traits_data: TraitsData):
        traits_data.addTrait(trait_id)
        for name, value in trait_properties.items():
            traits_data.setTraitProperty(trait_id, name, value)

    def __validate_access(
        self,
        function_name: str,
        allowed_access: Iterable,
        access,
        batch_elems: List[Any],
        error_callback,
    ):
        if access in allowed_access:
            return True
        for idx, _ in enumerate(batch_elems):
            error_callback(
                idx,
                BatchElementError(
                    BatchElementError.ErrorCode.kEntityAccessError,
                    f"Unsupported access mode for {function_name}",
                ),
            )
        return False

    @staticmethod
    def __handle_exception(exc, idx, error_callback):
        """
        Calls the error_callback with an appropriate BatchElementError
        depending on the caught exception.

        Other, exceptional exceptions are re-thrown.
        """
        msg = str(exc)

        if isinstance(exc, MalformedEntityReference):
            code = BatchElementError.ErrorCode.kMalformedEntityReference
        elif isinstance(exc, bal.UnknownBALEntity):
            code = BatchElementError.ErrorCode.kEntityResolutionError
        elif isinstance(exc, bal.InvalidEntityVersion):
            code = BatchElementError.ErrorCode.kEntityResolutionError
        elif isinstance(exc, bal.InaccessibleEntity):
            code = BatchElementError.ErrorCode.kEntityAccessError
        else:
            raise exc

        error_callback(idx, BatchElementError(code, msg))

    @staticmethod
    def __make_default_settings() -> dict:
        """
        Generates a default settings dict for BAL.
        Note: as a library is required, the default settings are not enough
        to initialize the manager.
        """
        return {
            SETTINGS_KEY_LIBRARY_PATH: "",
            SETTINGS_KEY_SIMULATED_QUERY_LATENCY: 10,
            SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME: "bal",
        }

    @staticmethod
    def __validate_settings(settings: dict):
        """
        Parses the supplied settings dict, raising if there are any
        unrecognized keys present.
        """
        defaults = BasicAssetLibraryInterface.__make_default_settings()

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

        if SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME in settings:
            scheme = settings[SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME]
            if not isinstance(scheme, str):
                raise ValueError(f"{SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME} must be a string")
            if not scheme:
                raise ValueError(f"{SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME} must not be empty")
            if not re.match(r"^[a-zA-Z0-9-]+$", scheme):
                raise ValueError(
                    f"{SETTINGS_KEY_ENTITY_REFERENCE_URL_SCHEME} '{scheme}' must only consist of "
                    "legal URL scheme characters (a-z, A-Z, 0-9, -)"
                )

        for key in settings:
            if key not in defaults:
                raise KeyError(f"Unknown setting '{key}'")


class BALEntityReferencePagerInterface(EntityReferencePagerInterface):
    """
    Simple implementation of a pager.

    Bulk-queries all data, then splits up into cached pages ready to
    regurgitate on demand.
    """

    def __init__(self, simulated_latency, page_size, entity_references):
        EntityReferencePagerInterface.__init__(self)
        self.simulated_latency = simulated_latency
        self.__page_num = 0
        self.__pages = []

        for page_start in range(0, len(entity_references), page_size):
            self.__pages.append(entity_references[page_start : page_start + page_size])

    @simulated_delay
    def hasNext(self, _hostSession):
        return self.__page_num < len(self.__pages) - 1

    @simulated_delay
    def next(self, _hostSession):
        self.__page_num += 1

    @simulated_delay
    def get(self, _hostSession):
        return self.__pages[self.__page_num] if self.__page_num < len(self.__pages) else []
