import json

import pytest

from modstride.cli import main
from modstride.mappings import lookup


def test_tiny_lookup_matches_owner_and_descriptor(tmp_path, capsys):
    table = tmp_path / "synthetic table.tiny"
    table.write_text(
        "tiny\t2\t0\tofficial\tintermediary\tnamed\n"
        "c\ta\tclass_100\tfixture/Example\n"
        "\tm\t(I)V\tx\tmethod_100\tcall\n"
        "\tm\t(J)V\tx\tmethod_101\tcall\n",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "mappings",
                "lookup",
                str(table),
                "--namespace",
                "named",
                "--owner",
                "fixture/Example",
                "--member",
                "call",
                "--descriptor",
                "(J)V",
            ]
        )
        == 0
    )
    found = json.loads(capsys.readouterr().out)
    assert found["names"]["intermediary"] == "method_101"
    assert found["descriptor_namespace"] == "official"
    assert (
        lookup(table, "intermediary", "class_100")["owner"]["named"]
        == "fixture/Example"
    )
    with pytest.raises(ValueError, match="Unknown mapping namespace"):
        lookup(table, "fictional", "a")
    with pytest.raises(ValueError, match="No exact symbol"):
        lookup(table, "official", "a", "x", "(D)V")
