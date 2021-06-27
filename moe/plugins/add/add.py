"""Adds music to the library."""

import argparse
import logging
import pathlib

import mediafile
import pluggy
from sqlalchemy.orm.session import Session

import moe
from moe.core.config import Config
from moe.core.library.album import Album
from moe.core.library.extra import Extra
from moe.core.library.lib_item import LibItem
from moe.core.library.track import Track
from moe.plugins.add import prompt

log = logging.getLogger(__name__)


class AddError(Exception):
    """Error adding an item to the library."""


class Hooks:
    """Add hooks."""

    @staticmethod
    @moe.hookspec
    def pre_add(config: Config, session: Session, album: Album) -> Album:
        """Return a new album with changes to be applied by the user via the prompt.

        Args:
            config: Moe config.
            session: Currrent db session.
            album: Original album to alter.

        Returns:
            The new, altered album to compare against the original in the prompt.
        """  # noqa: DAR202


@moe.hookimpl
def add_hooks(plugin_manager: pluggy.manager.PluginManager):
    """Registers `add` hookspecs to Moe."""
    from moe.plugins.add.add import Hooks  # noqa: WPS433, WPS442

    plugin_manager.add_hookspecs(Hooks)


@moe.hookimpl
def add_command(cmd_parsers: argparse._SubParsersAction):  # noqa: WPS437
    """Adds the ``add`` command to Moe's CLI."""
    add_parser = cmd_parsers.add_parser(
        "add", description="Adds music to the library.", help="add music to the library"
    )
    add_parser.add_argument(
        "paths",
        metavar="path",
        nargs="+",
        help="dir to add an album or file to add a track",
    )
    add_parser.set_defaults(func=parse_args)


def parse_args(config: Config, session: Session, args: argparse.Namespace):
    """Parses the given commandline arguments.

    Tracks can be added as files or albums as directories.

    Args:
        config: Moe config.
        session: Current db session.
        args: Commandline arguments to parse.

    Raises:
        SystemExit: Path given does not exist.
    """
    paths = [pathlib.Path(arg_path) for arg_path in args.paths]

    error_count = 0
    for path in paths:
        try:
            add_item(config, session, path)
        except AddError as exc:
            log.error(exc)
            error_count += 1

    if error_count:
        raise SystemExit(1)


def add_item(config: Config, session: Session, item_path: pathlib.Path):
    """Adds a LibItem to the library from a given path.

    Args:
        config: Moe config.
        session: Current db session.
        item_path: Filesystem path of the item.

    Raises:
        AddError: Unable to add the item to the library.
    """
    item: LibItem
    if item_path.is_file():
        item = _add_track(item_path)
        old_album = item.album_obj
    elif item_path.is_dir():
        item = _add_album(item_path)
        old_album = item
    else:
        raise AddError(f"Path not found: {item_path}")

    old_album.merge(old_album.get_existing(session), overwrite_album_info=False)
    new_albums = config.plugin_manager.hook.pre_add(
        config=config, session=session, album=old_album
    )
    if new_albums:
        add_album = prompt.run_prompt(config, session, old_album, new_albums[0])
    else:
        add_album = old_album

    if add_album:
        session.merge(add_album)


def _add_album(album_path: pathlib.Path) -> Album:
    """Add an album to the library from a given directory.

    Args:
        album_path: Filesystem path of the album directory to add.

    Returns:
        Album added.

    Raises:
        AddError: Unable to add the album to the library.
    """
    log.info(f"Adding album to the library: {album_path}")

    album_tracks = []
    extra_paths = []
    for file_path in album_path.rglob("*"):
        try:
            album_tracks.append(Track.from_tags(path=file_path))
        except (TypeError, mediafile.UnreadableFileError):
            extra_paths.append(file_path)

    if not album_tracks:
        raise AddError(f"No tracks found in album: {album_path}")

    albums = [track.album_obj for track in album_tracks]

    # ensure each track belongs to the same album
    for discovered_album in albums:
        if not albums[0].has_eq_keys(discovered_album):
            raise AddError(
                f"Not all tracks in '{album_path}' share the same album attributes."
            )

    album = albums[0]
    for track in album_tracks:
        log.info(f"Adding track file to the library: {track.path}")
        album.tracks.append(track)

    for extra_path in extra_paths:
        log.info(f"Adding extra file to the library: {extra_path}")
        Extra(extra_path, album)

    return album


def _add_track(track_path: pathlib.Path) -> Track:
    """Add a track to the library from a given file.

    The Track's attributes are populated from the tags read at `track_path`.

    Args:
        track_path: Filesystem path of the track file to add.

    Returns:
        Track added.

    Raises:
        AddError: Unable to add the track to the library.
    """
    log.info(f"Adding track to the library: {track_path}")

    try:
        track = Track.from_tags(path=track_path)
    except (TypeError, mediafile.UnreadableFileError) as init_exc:
        raise AddError(init_exc) from init_exc

    return track