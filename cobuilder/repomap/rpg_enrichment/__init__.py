"""RPG Enrichment pipeline for the Repository Planning Graph.

This package provides the encoder-based enrichment pipeline that
processes an RPGGraph through a sequence of RPGEncoder stages,
adding type annotations, signatures, docstrings, and other metadata.
"""

from cobuilder.repomap.rpg_enrichment.base import RPGEncoder
from cobuilder.repomap.rpg_enrichment.baseclass_encoder import BaseClassEncoder
from cobuilder.repomap.rpg_enrichment.dataflow_encoder import DataFlowEncoder
from cobuilder.repomap.rpg_enrichment.file_encoder import FileEncoder
from cobuilder.repomap.rpg_enrichment.folder_encoder import FolderEncoder
from cobuilder.repomap.rpg_enrichment.interface_design_encoder import InterfaceDesignEncoder
from cobuilder.repomap.rpg_enrichment.models import EncoderStep, ValidationResult
from cobuilder.repomap.rpg_enrichment.ordering_encoder import IntraModuleOrderEncoder
from cobuilder.repomap.rpg_enrichment.pipeline import RPGBuilder
from cobuilder.repomap.rpg_enrichment.serena_validator import SerenaValidator

__all__ = [
    "BaseClassEncoder",
    "DataFlowEncoder",
    "EncoderStep",
    "FileEncoder",
    "FolderEncoder",
    "InterfaceDesignEncoder",
    "IntraModuleOrderEncoder",
    "RPGBuilder",
    "RPGEncoder",
    "SerenaValidator",
    "ValidationResult",
]
