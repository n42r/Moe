"""Test the list plugin."""

import argparse
import pathlib
from unittest.mock import Mock

import pytest

from moe import cli
from moe.core import library
from moe.plugins import ls


class TestParseArgs:
    """Test music is listed from the database when invoked."""

    def test_track(self, capsys, tmp_session):
        """Tracks are printed to stdout."""
        args = argparse.Namespace(query="id:1")

        tmp_session.add(library.Track(path=pathlib.Path("/tmp_path")))
        tmp_session.commit()

        ls.parse_args(Mock(), tmp_session, args)

        captured_text = capsys.readouterr()

        assert captured_text.out


@pytest.mark.integration
class TestCommand:
    """Test cli integration with the ls command."""

    def test_parse_args(self, capsys, tmp_live, add_track):
        """Music is listed from the library when the `ls` command is invoked."""
        config, pm = tmp_live

        args = ["ls", "id:1"]
        cli._parse_args(args, pm, config)

        captured_text = capsys.readouterr()

        assert captured_text.out
