"""Adds music to the library.

This module provides the main entry point into the add process via ``add_item()``.
"""

import logging

import pluggy

import moe
from moe.config import Config, MoeSession
from moe.library.lib_item import LibItem

__all__ = ["AddAbortError", "AddError", "add_item"]

log = logging.getLogger("moe.add")


class Hooks:
    """Add plugin hook specifications."""

    @staticmethod
    @moe.hookspec
    def pre_add(config: Config, item: LibItem):
        """Provides an item prior to it being added to the library.

        Use this hook if you wish to change an item's metadata prior to it being
        added to the library.

        Args:
            config: Moe config.
            item: Library item being added.

        Note:
            Any UI application should have a way of detecting and resolving duplicate
            items prior to them being added to the database. You may consider
            implementing a ``hookwrapper`` to run conflict resolution code after the
            ``pre_add`` hook is complete, but before the item has been added to the db.

        See Also:
            * The :meth:`~moe.library.lib_item.Hooks.edit_new_items` hook for editing
              items that have been added
              to the library.
            * `Pluggy hook wrapper documention
              <https://pluggy.readthedocs.io/en/stable/#wrappers>`_
        """


@moe.hookimpl
def add_hooks(pm: pluggy.manager.PluginManager):
    """Registers `add` hookspecs to Moe."""
    from moe.plugins.add.add_core import Hooks

    pm.add_hookspecs(Hooks)


class AddError(Exception):
    """Error adding an item to the library."""


class AddAbortError(Exception):
    """Add process has been aborted by the user."""


def add_item(config: Config, item: LibItem):
    """Adds a LibItem to the library.

    Args:
        config: Moe config.
        item: Item to be added.

    Raises:
        AddError: Unable to add the item to the library.
    """
    log.debug(f"Adding item to the library. [{item=!r}]")
    session = MoeSession()

    config.pm.hook.pre_add(config=config, item=item)
    session.add(item)
    session.flush()

    log.info(f"Item added to the library. [{item=!r}]")
