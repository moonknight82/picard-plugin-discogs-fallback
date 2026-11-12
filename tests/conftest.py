"""Make the plugin package importable from any checkout directory name."""

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if ROOT.name == "picard_plugin_discogs_fallback":
    sys.path.insert(0, str(ROOT.parent))
else:
    spec = importlib.util.spec_from_file_location(
        "picard_plugin_discogs_fallback",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
