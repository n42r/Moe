"""Core api for moving items."""

import logging
import re
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Union

import dynaconf
from unidecode import unidecode

import moe
from moe.config import Config
from moe.library.album import Album
from moe.library.extra import Extra
from moe.library.lib_item import LibItem
from moe.library.track import Track

__all__ = ["copy_item", "fmt_item_path", "move_item"]

log = logging.getLogger("moe.move")


@moe.hookimpl
def add_config_validator(settings: dynaconf.base.LazySettings):
    """Validate move plugin configuration settings."""
    default_album_path = "{album.artist}/{album.title} ({album.year})"
    default_extra_path = "{extra.path.name}"
    default_track_path = (
        "{f'Disc {track.disc:02}' if track.disc_total > 1 else ''}/"
        "{track.track_num:02} - {track.title}{track.path.suffix}"
    )

    validators = [
        dynaconf.Validator("MOVE.ASCIIFY_PATHS", default=False),
        dynaconf.Validator("MOVE.ALBUM_PATH", default=default_album_path),
        dynaconf.Validator("MOVE.EXTRA_PATH", default=default_extra_path),
        dynaconf.Validator("MOVE.TRACK_PATH", default=default_track_path),
    ]
    settings.validators.register(*validators)


@moe.hookimpl(trylast=True)
def edit_new_items(config: Config, items: list[LibItem]):
    """Copies and formats the path of an item after it has been added to the library."""
    for item in items:
        copy_item(config, item)


########################################################################################
# Format paths
########################################################################################
def fmt_item_path(config: Config, item: LibItem) -> Path:
    """Returns a formatted item path according to the user configuration."""
    log.debug(f"Formatting item path. [path={item.path}]")

    if isinstance(item, Album):
        new_path = _fmt_album_path(config, item)
    elif isinstance(item, Extra):
        new_path = _fmt_extra_path(config, item)
    elif isinstance(item, Track):
        new_path = _fmt_track_path(config, item)
    else:
        raise NotImplementedError

    if config.settings.move.asciify_paths:
        new_path = Path(unidecode(str(new_path)))

    log.debug(f"Formatted item path. [path={new_path}]")
    return new_path


def _fmt_album_path(config: Config, album: Album) -> Path:
    """Returns a formatted album directory according to the user configuration."""
    library_path = Path(config.settings.library_path).expanduser()
    album_path = _eval_path_template(config.settings.move.album_path, album)

    return library_path / album_path


def _fmt_extra_path(config: Config, extra: Extra) -> Path:
    """Returns a formatted extra path according to the user configuration."""
    album_path = _fmt_album_path(config, extra.album_obj)
    extra_path = _eval_path_template(config.settings.move.extra_path, extra)

    return album_path / extra_path


def _fmt_track_path(config: Config, track: Track) -> Path:
    """Returns a formatted track path according to the user configuration."""
    album_path = _fmt_album_path(config, track.album_obj)
    track_path = _eval_path_template(config.settings.move.track_path, track)

    return album_path / track_path


def _eval_path_template(template, lib_item) -> str:
    """Evaluates and sanitizes a path template.

    Args:
        template: Path template.
            See `_lazy_fstr_item()` for more info on accepted f-string templates.
        lib_item: Library item associated with the template.

    Returns:
        Evaluated path.
    """
    template_parts = template.split("/")
    sanitized_parts = []
    for template_part in template_parts:
        path_part = _lazy_fstr_item(template_part, lib_item)
        sanitized_part = _sanitize_path_part(path_part)
        if sanitized_part:
            sanitized_parts.append(sanitized_part)

    return "/".join(sanitized_parts)


def _lazy_fstr_item(template: str, lib_item: LibItem) -> str:
    """Evalutes the given f-string template for a specific library item.

    Args:
        template: f-string template to evaluate.
            All library items should have their own template and refer to variables as:
                Album: album (e.g. {album.title}, {album.artist})
                Track: track (e.g. {track.title}, {track.artist})
                Extra: extra (e.g. {extra.path.name}
        lib_item: Library item referenced in the template.


    Example:
        The default path template for an album is::

            {album.artist}/{album.title} ({album.year})

    Returns:
        Evaluated f-string.

    Raises:
        NotImplementedError: You discovered a new library item!
    """
    # add the appropriate library item to the scope
    if isinstance(lib_item, Album):
        album = lib_item  # noqa: F841
    elif isinstance(lib_item, Track):
        track = lib_item  # noqa: F841
    elif isinstance(lib_item, Extra):
        extra = lib_item  # noqa: F841
    else:
        raise NotImplementedError

    return eval(f'f"""{template}"""')


def _sanitize_path_part(path_part: str) -> str:
    """Sanitizes a part of a path to be compatible with most filesystems.

    Note:
        Only sub-paths of the library path will be affected.

    Args:
        path_part: Path part to sanitize. Must be a single 'part' of a path, i.e. no /
            separators.

    Returns:
        Path part with all the replacements applied.
    """
    PATH_REPLACE_CHARS = {
        r"^\.": "_",  # leading '.' (hidden files on Unix)
        r'[<>:"\?\*\|\\/]': "_",  # <, >, : , ", ?, *, |, \, / (Windows reserved chars)
        r"\.$": "_",  # trailing '.' (Windows restriction)
        r"\s+$": "",  # trailing whitespace (Windows restriction)
    }

    for regex, replacement in PATH_REPLACE_CHARS.items():
        path_part = re.sub(regex, replacement, path_part)

    return path_part


########################################################################################
# Copy
########################################################################################
def copy_item(config: Config, item: LibItem):
    """Copies an item to a destination as determined by the user configuration.

    Overwrites any existing files. Will create the destination if it does not already
    exist.
    """
    if isinstance(item, Album):
        _copy_album(config, item)
    elif isinstance(item, (Extra, Track)):
        _copy_file_item(config, item)


def _copy_album(config: Config, album: Album):
    """Copies an album to a destination as determined by the user configuration."""
    dest = fmt_item_path(config, album)

    log.debug(f"Copying album. [{dest=}, {album=!r}]")

    if album.path != dest:
        dest.mkdir(parents=True, exist_ok=True)
        album.path = dest

    for track in album.tracks:
        _copy_file_item(config, track)

    for extra in album.extras:
        _copy_file_item(config, extra)

    log.info(f"Album copied. [{dest=}, {album=!r}]")


def _copy_file_item(config: Config, item: Union[Extra, Track]):
    """Copies an extra or track to a destination as determined by the user config."""
    dest = fmt_item_path(config, item)
    log.debug(f"Copying item. [{dest=}, {item=!r}]")

    if dest == item.path:
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(item.path, dest)

    item.path = dest

    log.info(f"Copied item. [{dest=}, {item=!r}]")


########################################################################################
# Move
########################################################################################
def move_item(config: Config, item: LibItem):
    """Moves an item to a destination as determined by the user configuration.

    Overwrites any existing files. Will create the destination if it does not already
    exist.
    """
    if isinstance(item, Album):
        _move_album(config, item)
    elif isinstance(item, (Extra, Track)):
        _move_file_item(config, item)


def _move_album(config: Config, album: Album):
    """Moves an album to a given destination.

    Note:
        Empty leftover directories will be removed.
    """
    dest = fmt_item_path(config, album)
    old_album_dir = album.path

    log.debug(f"Moving album. [{dest=}, {album=!r}]")

    if album.path != dest:
        dest.mkdir(parents=True, exist_ok=True)
        album.path = dest

    for track in album.tracks:
        _move_file_item(config, track)

    for extra in album.extras:
        _move_file_item(config, extra)

    # remove any empty leftover directories
    for old_child in old_album_dir.rglob("*"):
        with suppress(OSError):
            old_child.rmdir()
    with suppress(OSError):
        old_album_dir.rmdir()
    for old_parent in old_album_dir.parents:
        with suppress(OSError):
            old_parent.rmdir()

    log.info(f"Moved album. [{dest=}, {album=!r}]")


def _move_file_item(config: Config, item: Union[Extra, Track]):
    """Moves an extra or track to a destination as determined by the user config."""
    dest = fmt_item_path(config, item)
    if dest == item.path:
        return

    log.debug(f"Moving item. [{dest=}, {item=!r}]")

    dest.parent.mkdir(parents=True, exist_ok=True)
    item.path.replace(dest)

    item.path = dest

    log.info(f"Moved item. [{dest=}, {item=!r}]")
