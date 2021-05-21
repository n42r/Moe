"""Adds music to the library."""

import argparse
import logging
import pathlib
from typing import List

import mediafile
from sqlalchemy.orm.session import Session

import moe
from moe.core.config import Config
from moe.core.library.album import Album
from moe.core.library.music_item import MusicItem
from moe.core.library.session import DbDupTrackPathError
from moe.core.library.track import Track

log = logging.getLogger(__name__)


class AddError(Exception):
    """Error adding an item to the library."""


class Hooks:
    """Add hooks."""

    @staticmethod
    @moe.hookspec
    def post_add(item: MusicItem):
        """Provides the MusicItem that was added to the library."""


@moe.hookimpl
def addcommand(cmd_parsers: argparse._SubParsersAction):  # noqa: WPS437
    """Adds a new `add` command to moe."""
    add_parser = cmd_parsers.add_parser(
        "add", description="Adds music to the library.", help="add music to the library"
    )
    add_parser.add_argument(
        "paths", nargs="+", help="dir to add an album or file to add a track"
    )
    add_parser.set_defaults(func=parse_args)


def parse_args(config: Config, session: Session, args: argparse.Namespace):
    """Parses the given commandline arguments.

    Args:
        config: Configuration in use.
        session: Current session.
        args: Commandline arguments to parse.

    Raises:
        SystemExit: Path given does not exist.
    """
    config.pluginmanager.add_hookspecs(Hooks)

    paths = [pathlib.Path(arg_path) for arg_path in args.paths]

    error_count = 0
    item_added: MusicItem
    for path in paths:
        if not path.exists():
            log.error(f"Path not found: {path}")
            error_count += 1

        try:
            if path.is_file():
                item_added = _add_track(path)
            elif path.is_dir():
                item_added = _add_album(path)
        except AddError as exc:
            log.error(exc)
            error_count += 1

    if error_count:
        raise SystemExit(1)

    config.pluginmanager.hook.post_add(item=item_added)


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
    album_tracks: List[Track] = []
    for file_path in album_path.rglob("*"):
        log.info(f"Adding track to the library: {file_path}")
        try:
            album_tracks.append(Track.from_tags(path=file_path))
        except (TypeError, mediafile.UnreadableFileError) as exc:
            log.warning(f"Could not add track to album: {str(exc)}")

    if not album_tracks:
        raise AddError(f"No tracks found in album: {album_path}")

    albums = [track._album_obj for track in album_tracks]  # noqa: WPS437

    # ensure every track belongs to the same album
    if albums.count(albums[0]) != len(albums):  # checks if each album is the same
        raise AddError(
            f"Not all tracks in '{album_path}' share the same album attributes."
        )

    for track in album_tracks:
        try:
            track.add_to_db()
        except DbDupTrackPathError as dup_exc:
            log.warning(dup_exc)

    return albums[0]  # we already ensured this list is just multiple of the same album


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

    try:
        track.add_to_db()
    except DbDupTrackPathError as db_exc:
        raise AddError(db_exc) from db_exc

    return track
