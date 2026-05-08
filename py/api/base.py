"""Base mixin for SherpaNoteAPI domain mixins.

Provides the ``_api`` property that gives each mixin type-safe
access to the shared SherpaNoteAPI instance and its services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import SherpaNoteAPI


class ApiBase:
    """Base class for API domain mixins.

    Each mixin accesses shared state through ``self._api``,
    which returns the SherpaNoteAPI instance (works because
    all mixins are composed into a single class via multiple inheritance).
    """

    @property
    def _api(self) -> SherpaNoteAPI:
        return self  # type: ignore[return-value]
