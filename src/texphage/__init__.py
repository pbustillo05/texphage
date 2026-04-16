from texphage.__version__ import __version__
from texphage.demacro import demacro
from texphage.find_packages import (
    PackageCall,
    find_command,
    find_explicit_package_calls,
    find_used_packages,
    get_dependencies,
)
from texphage.pipeline import Attachment, build_minimal_preamble, texphage, texphage_to_dir
from texphage.semantex import annotate, parse, process
from texphage.unfold import unfold

__all__ = [
    "__version__",
    # Main API
    "texphage",
    "texphage_to_dir",
    "build_minimal_preamble",
    "Attachment",
    # SemanTex API
    "parse",
    "annotate",
    "process",
    # Lower-level API
    "unfold",
    "demacro",
    "find_explicit_package_calls",
    "find_used_packages",
    "get_dependencies",
    "find_command",
    "PackageCall",
]
