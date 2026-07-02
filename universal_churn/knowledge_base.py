"""Compatibility shim for the typed business knowledge base.

The repository's implementation file is spelled `konwledge_base.py`.
This module re-exports its public names so existing imports using the
canonical `knowledge_base` module path keep working.
"""

from .konwledge_base import *  # noqa: F401,F403