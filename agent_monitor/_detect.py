"""Auto-detect which agent frameworks and OpenInference instrumentors are usable.

Two layers:
- Layer A: scan which frameworks are *importable* in the current Python env
  (langchain_core / openai / llama_index.core / etc.) via importlib.util.find_spec.
- Layer B: scan which OpenInference instrumentors are *installed* via entry_points.

Cross-referencing gives the set of frameworks for which auto-instrumentation
will actually work in this environment. Returned names are the *framework keys*
used by agent_monitor (e.g. "langchain", "openai"), not package names.
"""
from __future__ import annotations
from typing import Iterable


# (framework_key, importable_module, instrumentor_package)
# Framework keys match what openinference-instrumentation-<X> registers under
# its entry_points "name" attribute (best-effort).
_FRAMEWORKS: dict[str, tuple[str, str]] = {
    "langchain":    ("langchain_core",              "openinference-instrumentation-langchain"),
    "openai":       ("openai",                      "openinference-instrumentation-openai"),
    "llama-index":  ("llama_index.core",            "openinference-instrumentation-llama-index"),
    "anthropic":    ("anthropic",                   "openinference-instrumentation-anthropic"),
    "google-genai": ("google.genai",                "openinference-instrumentation-google-genai"),
    "groq":         ("groq",                        "openinference-instrumentation-groq"),
    "dspy":         ("dspy",                        "openinference-instrumentation-dspy"),
    "autogen":      ("autogen",                     "openinference-instrumentation-autogen"),
    "haystack":     ("haystack",                    "openinference-instrumentation-haystack"),
    "smolagents":   ("smolagents",                  "openinference-instrumentation-smolagents"),
    "crewai":       ("crewai",                      "openinference-instrumentation-crewai"),
    "bedrock":      ("boto3",                       "openinference-instrumentation-bedrock"),
    "litellm":      ("litellm",                     "openinference-instrumentation-litellm"),
}


def detect_installed_frameworks() -> list[str]:
    """Frameworks whose top-level module is importable in this env."""
    import importlib.util
    found: list[str] = []
    for name, (mod, _pkg) in _FRAMEWORKS.items():
        # Split into top-level + sub-modules; check the top-level first.
        top = mod.split(".")[0]
        try:
            if importlib.util.find_spec(top) is None:
                continue
        except (ModuleNotFoundError, ValueError):
            continue
        # If the spec is for a submodule, find_spec can still raise when the
        # parent package exists but the submodule does not. Wrap defensively.
        try:
            if importlib.util.find_spec(mod) is None:
                continue
        except (ModuleNotFoundError, ValueError, ImportError):
            continue
        found.append(name)
    return found


def detect_installed_instrumentors() -> list[str]:
    """OpenInference instrumentors whose entry_points are registered here.

    Returns the raw `entry_points(name=...)` values, which may be either the
    short name (e.g. "langchain") or the full package name (e.g.
    "openinference-instrumentation-langchain") depending on the package.
    """
    from importlib.metadata import entry_points
    eps = entry_points()
    try:
        group = eps.select(group="openinference_instrumentor")
    except AttributeError:
        group = eps.get("openinference_instrumentor", [])  # type: ignore[arg-type]
    return [ep.name for ep in group]


def _normalize_instrumentor_name(name: str) -> str:
    """Map an entry_point name to its framework key (best-effort)."""
    short = name.replace("openinference-instrumentation-", "")
    for fw_key, (_mod, pkg) in _FRAMEWORKS.items():
        if short == pkg.replace("openinference-instrumentation-", ""):
            return fw_key
        if name == pkg:
            return fw_key
        if name == fw_key:
            return fw_key
    return short


def detect_compatible(candidates: Iterable[str] | None = None) -> list[str]:
    """Frameworks that are BOTH importable AND have an installed instrumentor.

    Args:
        candidates: optional whitelist of framework keys to restrict the search.
            If None, every known framework is considered.

    Returns:
        list of framework keys in stable order (matches _FRAMEWORKS insertion).
    """
    frameworks = set(detect_installed_frameworks())
    raw_inst = detect_installed_instrumentors()
    normalized = {_normalize_instrumentor_name(n) for n in raw_inst}
    if candidates is not None:
        frameworks = frameworks & set(candidates)
    compatible: list[str] = []
    for fw_key in _FRAMEWORKS:
        if fw_key in frameworks and fw_key in normalized:
            compatible.append(fw_key)
    return compatible


def detect_all() -> dict[str, list[str]]:
    """Diagnostic dump: everything we can see, in one dict."""
    return {
        "installed_frameworks":     detect_installed_frameworks(),
        "installed_instrumentors":  detect_installed_instrumentors(),
        "compatible":               detect_compatible(),
    }


def list_supported_frameworks() -> list[str]:
    """All framework keys this SDK knows about (for CLI listings)."""
    return list(_FRAMEWORKS.keys())
# PyPI packages that provide the *framework SDK* (not the OpenInference
# instrumentor). Used by `python -m agent_monitor init --framework auto` to
# install everything a brand-new project needs in one shot. The OI
# instrumentor itself is installed via `agent-monitor[<framework_key>]`
# in __main__.py.
_FRAMEWORK_SDK_PACKAGES: dict[str, list[str]] = {
    "langchain":    ["langchain", "langchain-openai", "openai"],
    "openai":       ["openai"],
    "llama-index":  ["llama-index", "openai"],
    "anthropic":    ["anthropic"],
    "google-genai": ["google-genai"],
    "groq":         ["groq"],
    "dspy":         ["dspy", "openai"],
    "autogen":      ["autogen-agentchat", "autogen-core", "openai"],
    "haystack":     ["haystack-ai", "openai"],
    "smolagents":   ["smolagents", "openai"],
    "crewai":       ["crewai", "openai"],
    "bedrock":      ["boto3"],
    "litellm":      ["litellm", "openai"],
}


def framework_sdk_packages(fw_key: str) -> list[str]:
    """PyPI packages that provide the framework SDK for ``fw_key``.

    Returns an empty list for unknown / composite frameworks. The matching
    OpenInference instrumentor (``agent-monitor[<fw_key>]``) is installed
    separately and is NOT included here.
    """
    return list(_FRAMEWORK_SDK_PACKAGES.get(fw_key, []))
