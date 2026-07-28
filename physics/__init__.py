"""Simulation backends for Contact Patch.

``schema`` is the single source of truth for units and sign conventions; every
other module in the project reads its conventions from there rather than
restating them.
"""

from .schema import SCHEMA_VERSION  # noqa: F401
