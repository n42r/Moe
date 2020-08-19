"""List music in the library."""

import argparse

import sqlalchemy

import moe
from moe.core import query
from moe.core.config import Config


@moe.hookimpl
def addcommand(cmd_parsers: argparse._SubParsersAction):  # noqa: WPS437
    """Adds a new `ls` command to moe.

    Args:
        cmd_parsers: contains all the sub-command parsers
    """
    add_parser = cmd_parsers.add_parser(
        "ls",
        aliases=["list"],
        description="Lists music from the library.",
        help="list music from the library",
        parents=[query.query_parser],
    )
    add_parser.set_defaults(func=parse_args)


def parse_args(
    config: Config, session: sqlalchemy.orm.session.Session, args: argparse.Namespace,
):
    """Parses the given commandline arguments.

    Args:
        config: configuration in use
        session: current session
        args: given commandline arguments

    Raises:
        SystemExit: Query returned no tracks.
    """
    tracks = query.query(args.query, session)

    if not tracks:
        raise SystemExit(1)

    for track in tracks:
        print(track)  # noqa: WPS421