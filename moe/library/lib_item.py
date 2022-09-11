"""Shared functionality between library albums, extras, and tracks."""

import functools
import logging
from pathlib import Path

import pluggy
import sqlalchemy
import sqlalchemy as sa
import sqlalchemy.event
import sqlalchemy.orm

import moe
from moe.config import Config

__all__ = ["LibItem", "LibraryError"]

log = logging.getLogger("moe.lib_item")


class LibraryError(Exception):
    """General library error."""


class Hooks:
    """General usage library item hooks."""

    @staticmethod
    @moe.hookspec
    def edit_changed_items(config: Config, items: list["LibItem"]):
        """Edit items in the library that were changed in some way.

        Args:
            config: Moe config.
            items: Any changed items that existed in the library prior to the current
                session.

        See Also:
            The :meth:`process_changed_items` hook for processing items with finalized
            values.
        """

    @staticmethod
    @moe.hookspec
    def edit_new_items(config: Config, items: list["LibItem"]):
        """Edit new items in the library.

        Args:
            config: Moe config.
            items: Any items being added to the library for the first time.

        See Also:
            The :meth:`process_new_items` hook for processing items with finalized
            values.
        """

    @staticmethod
    @moe.hookspec
    def process_removed_items(config: Config, items: list["LibItem"]):
        """Process items that have been removed from the library.

        Args:
            config: Moe config.
            items: Any items that existed in the library prior to the current session,
                but have now been removed from the library.
        """

    @staticmethod
    @moe.hookspec
    def process_changed_items(config: Config, items: list["LibItem"]):
        """Process items in the library that were changed in some way.

        Args:
            config: Moe config.
            items: Any changed items that existed in the library prior to the current
                session.

        Important:
            Any changes made to the items will be lost.

        See Also:
            The :meth:`edit_changed_items` hook for editing items before their values
            are finalized.
        """

    @staticmethod
    @moe.hookspec
    def process_new_items(config: Config, items: list["LibItem"]):
        """Process new items in the library.

        Args:
            config: Moe config.
            items: Any items being added to the library for the first time.

        Important:
            Any changes made to the items will be lost.

        See Also:
            The :meth:`edit_new_items` hook for editing items before their values are
            finalized.
        """


@moe.hookimpl
def add_hooks(plugin_manager: pluggy.manager.PluginManager):
    """Registers `add` hookspecs to Moe."""
    from moe.library.lib_item import Hooks

    plugin_manager.add_hookspecs(Hooks)


@moe.hookimpl
def register_sa_event_listeners(config: Config, session: sqlalchemy.orm.Session):
    """Registers event listeners for editing and processing new items."""
    sqlalchemy.event.listen(
        session,
        "before_flush",
        functools.partial(_edit_before_flush, config=config),
    )
    sqlalchemy.event.listen(
        session,
        "after_flush",
        functools.partial(_process_after_flush, config=config),
    )


def _edit_before_flush(
    session: sqlalchemy.orm.Session,
    flush_context: sqlalchemy.orm.UOWTransaction,
    instances,
    config: Config,
):
    """Runs the ``edit_*_items`` hook specifications before items are flushed.

    This uses the sqlalchemy ORM event ``before_flush`` in the background to determine
    the time of execution and to provide any new, changed, or deleted items to the hook
    implementations.

    Args:
        session: Current db session.
        flush_context: sqlalchemy obj which handles the details of the flush.
        instances: Objects passed to the `session.flush()` method (deprecated).
        config: Moe config.

    See Also:
        `SQLAlchemy docs on state management <https://docs.sqlalchemy.org/en/14/orm/session_state_management.html>`_
    """  # noqa: E501
    changed_items = []
    for dirty_item in session.dirty:
        if session.is_modified(dirty_item) and isinstance(dirty_item, LibItem):
            changed_items.append(dirty_item)
    if changed_items:
        log.debug(f"Editing changed items. [{changed_items=!r}]")
        config.plugin_manager.hook.edit_changed_items(
            config=config, items=changed_items
        )
        log.debug(f"Edited changed items. [{changed_items=!r}]")

    new_items = []
    for new_item in session.new:
        if isinstance(new_item, LibItem):
            new_items.append(new_item)
    if new_items:
        log.debug(f"Editing new items. [{new_items=!r}]")
        config.plugin_manager.hook.edit_new_items(config=config, items=new_items)
        log.debug(f"Edited new items. [{new_items=!r}]")


def _process_after_flush(
    session: sqlalchemy.orm.Session,
    flush_context: sqlalchemy.orm.UOWTransaction,
    config: Config,
):
    """Runs the ``process_*_items`` hook specifications after items are flushed.

    This uses the sqlalchemy ORM event ``after_flush`` in the background to determine
    the time of execution and to provide any new, changed, or deleted items to the hook
    implementations.

    Args:
        session: Current db session.
        flush_context: sqlalchemy obj which handles the details of the flush.
        config: Moe config.

    See Also:
        `SQLAlchemy docs on state management <https://docs.sqlalchemy.org/en/14/orm/session_state_management.html>`_
    """  # noqa: E501
    changed_items = []
    for dirty_item in session.dirty:
        if session.is_modified(dirty_item) and isinstance(dirty_item, LibItem):
            changed_items.append(dirty_item)
    if changed_items:
        log.debug(f"Processing changed items. [{changed_items=!r}]")
        config.plugin_manager.hook.process_changed_items(
            config=config, items=changed_items
        )
        log.debug(f"Processed changed items. [{changed_items=!r}]")

    new_items = []
    for new_item in session.new:
        if isinstance(new_item, LibItem):
            new_items.append(new_item)
    if new_items:
        log.debug(f"Processing new items. [{new_items=!r}]")
        config.plugin_manager.hook.process_new_items(config=config, items=new_items)
        log.debug(f"Processed new items. [{new_items=!r}]")

    removed_items = []
    for removed_item in session.deleted:
        if isinstance(removed_item, LibItem):
            removed_items.append(removed_item)
    if removed_items:
        log.debug(f"Processing removed items. [{removed_items=!r}]")
        config.plugin_manager.hook.process_removed_items(
            config=config, items=removed_items
        )
        log.debug(f"Processed removed items. [{removed_items=!r}]")


class LibItem:
    """Abstract base class for library items i.e. Albums, Extras, and Tracks."""

    @property
    def path(self):
        """A library item's filesystem path."""
        raise NotImplementedError

    def fields(self) -> tuple[str, ...]:
        """Returns the public attributes of an item."""
        raise NotImplementedError

    def is_unique(self, other: "LibItem") -> bool:
        """Returns whether an item is unique in the library from ``other``."""
        raise NotImplementedError

    def __getattr__(self, name: str):
        """See if ``name`` is a custom field."""
        if name in self.custom_fields:
            return self._custom_fields[name]
        else:
            raise AttributeError from None

    def __setattr__(self, name, value):
        """Set custom custom_fields if a valid key."""
        if name in self.custom_fields:
            self._custom_fields[name] = value
        else:
            super().__setattr__(name, value)


class PathType(sa.types.TypeDecorator):
    """A custom type for paths for database storage.

    Normally, paths are Path type, but we can't store that in the database,
    so we normalize the paths first to strings for database storage. Paths are stored as
    relative paths from ``library_path`` in the config.
    """

    impl = sa.types.String  # sql type
    cache_ok = True  # expected to produce same bind/result behavior and sql generation

    library_path: Path  # will be set on config initialization

    def process_bind_param(self, pathlib_path, dialect):
        """Normalize pathlib paths as strings for the database.

        Args:
            pathlib_path: Inbound path to the db.
            dialect: Database in use.

        Returns:
            Relative path from ``library_path`` if possible, otherwise stores the
            absolute path.
        """
        try:
            return str(pathlib_path.relative_to(self.library_path))
        except ValueError:
            return str(pathlib_path.resolve())

    def process_result_value(self, path_str, dialect):
        """Convert the path back to a Path object on the way out."""
        if path_str is None:
            return None

        return Path(self.library_path / path_str)
