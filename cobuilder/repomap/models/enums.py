"""Enumerations for the Repository Planning Graph data model."""

from enum import Enum


class NodeLevel(str, Enum):
    """Hierarchical level of a node in the RPG."""

    MODULE = "MODULE"
    COMPONENT = "COMPONENT"
    FEATURE = "FEATURE"


class NodeType(str, Enum):
    """Type classification for RPG nodes."""

    FUNCTIONALITY = "FUNCTIONALITY"
    FOLDER_AUGMENTED = "FOLDER_AUGMENTED"
    FILE_AUGMENTED = "FILE_AUGMENTED"
    FUNCTION_AUGMENTED = "FUNCTION_AUGMENTED"


class InterfaceType(str, Enum):
    """Interface type for FUNCTION_AUGMENTED nodes."""

    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"


class TestStatus(str, Enum):
    """Test execution status for a node."""

    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DeltaStatus(str, Enum):
    """Delta status for nodes in a baseline-aware RPG.

    Indicates whether a node is new (not in the baseline), existing
    (unchanged from baseline), or modified (present in baseline but
    changed in the new spec).
    """

    NEW = "new"
    EXISTING = "existing"
    MODIFIED = "modified"


class EdgeType(str, Enum):
    """Type classification for RPG edges."""

    HIERARCHY = "HIERARCHY"
    DATA_FLOW = "DATA_FLOW"
    ORDERING = "ORDERING"
    INHERITANCE = "INHERITANCE"
    INVOCATION = "INVOCATION"
