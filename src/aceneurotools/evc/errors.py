"""Exception hierarchy for the experiment version control (EVC) subpackage."""

from __future__ import annotations


class EVCError(Exception):
    """Base class for all experiment-version-control errors."""


class RepositoryNotFoundError(EVCError):
    """No .evc repository exists at (or above) the given directory."""


class RepositoryExistsError(EVCError):
    """Attempted to initialise a repository where one already exists."""


class ObjectNotFoundError(EVCError):
    """A requested object id does not exist in the object store."""


class AmbiguousIdError(EVCError):
    """A short object-id prefix matches more than one stored object."""


class CorruptObjectError(EVCError):
    """Stored bytes do not hash to their object id (integrity failure)."""


class InvalidObjectError(EVCError):
    """An object body cannot be parsed or violates format constraints."""


class RefConflictError(EVCError):
    """A compare-and-set ref update found an unexpected current value."""


class UnknownRevisionError(EVCError):
    """A revision string cannot be resolved to a commit."""


class NothingToRecordError(EVCError):
    """The working state is identical to the current head revision."""


class PushRejectedError(EVCError):
    """A push was refused (non-fast-forward or unverifiable remote state)."""


class ManifestError(EVCError):
    """A run's artifact manifest is missing, malformed, or unsupported."""
