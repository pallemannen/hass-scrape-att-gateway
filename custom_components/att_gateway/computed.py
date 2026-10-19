"""Compute entity state off the event loop.

Entity properties (native_value, is_on, ...) run on the event loop at every
state write. Ours evaluate CSS selectors against a gateway page, and on a large
page a selector can take seconds or minutes (see the NAT table fix in 1.3.3),
which would freeze all of Home Assistant. Entities therefore implement
`_compute_<property>()` instead of the property. This mixin runs those methods
in the executor once per coordinator update, and once before the first state
write, and the properties only return the stored results.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

COMPUTED = ("native_value", "is_on", "current_option", "extra_state_attributes")


class ComputedStateMixin:
    """Run selector-based state computation in the executor.

    Must come before CoordinatorEntity in the class bases.
    """

    _computed: dict[str, Any] | None = None
    _compute_task: asyncio.Task | None = None
    _compute_again = False

    def _compute_all(self) -> dict[str, Any]:
        """Compute every property this entity defines. Runs in the executor."""
        return {
            name: getattr(self, f"_compute_{name}")()
            for name in COMPUTED
            if hasattr(self, f"_compute_{name}")
        }

    async def _async_compute(self) -> None:
        """Refresh the stored values; keep the previous ones if computing fails."""
        try:
            self._computed = await self.hass.async_add_executor_job(self._compute_all)
        except Exception:  # noqa: BLE001 - one entity's parse error must not stop updates
            _LOGGER.exception("Error computing state for %s", self.entity_id)

    async def async_added_to_hass(self) -> None:
        """Compute the initial state before the first state write."""
        await super().async_added_to_hass()
        await self._async_compute()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute in the executor, then write the state."""
        if self._compute_task is not None and not self._compute_task.done():
            self._compute_again = True
            return
        self._compute_task = self.hass.async_create_task(self._async_compute_and_write())

    async def _async_compute_and_write(self) -> None:
        while True:
            self._compute_again = False
            await self._async_compute()
            self.async_write_ha_state()
            if not self._compute_again:
                return

    def _stored(self, name: str) -> Any:
        return (self._computed or {}).get(name)

    @property
    def native_value(self) -> Any:
        """Return the stored value, if this entity computes it."""
        if hasattr(self, "_compute_native_value"):
            return self._stored("native_value")
        return super().native_value  # type: ignore[misc]

    @property
    def is_on(self) -> bool | None:
        """Return the stored state, if this entity computes it."""
        if hasattr(self, "_compute_is_on"):
            return self._stored("is_on")
        return super().is_on  # type: ignore[misc]

    @property
    def current_option(self) -> str | None:
        """Return the stored option, if this entity computes it."""
        if hasattr(self, "_compute_current_option"):
            return self._stored("current_option")
        return super().current_option  # type: ignore[misc]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the stored attributes, if this entity computes them."""
        if hasattr(self, "_compute_extra_state_attributes"):
            return self._stored("extra_state_attributes")
        return super().extra_state_attributes  # type: ignore[misc]
