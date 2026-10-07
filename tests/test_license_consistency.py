"""The licence consistency check: identifying a licence, and comparing prose.

The check runs in CI against the real repository; what is worth testing here is
the part that decides, because a guard that identifies licences wrongly is worse
than none -- it would pass a mismatched pair, or fail a matching one.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_license_consistency", REPO_ROOT / "tools" / "check_license_consistency.py"
)
checker = importlib.util.module_from_spec(_spec)
sys.modules["check_license_consistency"] = checker
_spec.loader.exec_module(checker)


# ---------------------------------------------------------------------------
# Identifying a licence from its own wording
# ---------------------------------------------------------------------------

#: The opening lines that actually distinguish these, rather than the whole
#: texts.  Each is what the checker keys on.
SAMPLES = {
    "GPL-2.0-only": (
        "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n"
        "Copyright (C) 1989, 1991 Free Software Foundation, Inc."
    ),
    "GPL-3.0-only": (
        "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n"
        "Copyright (C) 2007 Free Software Foundation, Inc."
    ),
    "LGPL-2.1-only": (
        "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999\n"
        "Copyright (C) 1991, 1999 Free Software Foundation, Inc.\n"
        "This license, the Lesser General Public License, applies to some\n"
        "specially designated software packages."
    ),
    "LGPL-3.0-only": (
        "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"
    ),
    "AGPL-3.0-only": (
        "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007"
    ),
    "Apache-2.0": (
        "Apache License\nVersion 2.0, January 2004\n"
        "http://www.apache.org/licenses/"
    ),
    "MPL-2.0": "Mozilla Public License Version 2.0\n1. Definitions",
    "MIT": (
        "MIT License\n\nCopyright (c) 2024 Someone\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a "
        "copy of this software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS "
        "OR IMPLIED."
    ),
    "ISC": "ISC License\n\nPermission to use, copy, modify, and/or distribute "
           "this software for any purpose with or without fee is hereby granted.",
    "BSD-3-Clause": (
        "Copyright (c) 2024, Someone\n"
        "Redistribution and use in source and binary forms, with or without\n"
        "modification, are permitted provided that the following conditions are "
        "met:\n\n3. Neither the name of the copyright holder nor the names of its "
        "contributors may be used to endorse or promote products."
    ),
    "BSD-2-Clause": (
        "Copyright (c) 2024, Someone\n"
        "Redistribution and use in source and binary forms, with or without\n"
        "modification, are permitted provided that the following conditions are "
        "met:"
    ),
}


@pytest.mark.parametrize("spdx", sorted(SAMPLES))
def test_each_supported_licence_is_identified(spdx):
    assert checker.identify(SAMPLES[spdx]) == spdx


def test_the_lesser_and_affero_licences_are_not_mistaken_for_the_gpl():
    """Both quote the GPL's heading, so the rules have to be tried most specific
    first.  Getting this wrong would report a mismatch between LGPL-2.1-only in
    the metadata and GPL-2.0-only in the file, which is a false alarm with a
    confusing message."""
    assert checker.identify(SAMPLES["LGPL-2.1-only"]) == "LGPL-2.1-only"
    assert checker.identify(SAMPLES["AGPL-3.0-only"]) == "AGPL-3.0-only"


def test_bsd_three_clause_is_not_mistaken_for_two_clause():
    """The three-clause text contains the whole of the two-clause text."""
    assert checker.identify(SAMPLES["BSD-3-Clause"]) == "BSD-3-Clause"
    assert checker.identify(SAMPLES["BSD-2-Clause"]) == "BSD-2-Clause"


def test_an_unrecognised_licence_is_reported_rather_than_guessed():
    assert checker.identify("This software is provided under the Wat Licence.") is None


def test_every_prose_name_maps_to_a_known_licence():
    """A prose spelling for a licence the checker cannot identify is dead weight."""
    known = {spdx for spdx, _ in checker.KNOWN_LICENCES}

    assert set(checker.PROSE_NAMES) <= known


# ---------------------------------------------------------------------------
# Reading prose
# ---------------------------------------------------------------------------

def test_a_licence_named_in_prose_is_found():
    assert checker.names_the_licence("licensed under the MIT licence", ("MIT",)) == ["MIT"]
    assert checker.names_the_licence("**License:** GPLv2", ("GPLv2",)) == ["GPLv2"]


@pytest.mark.parametrize("prose, names", [
    # Every one of these is a real word that contains a licence's spelling, and
    # all three made the first version of this script claim CONTRIBUTING.rst
    # mentioned licences it has never heard of.
    ("this is a discussion of the issue", ("ISC",)),
    ("please commit and submit the patch", ("MIT",)),
    ("for example, a limit", ("MPL", "MIT")),
    ("the examination", ("MIT", "MPL")),
    ("", ("MIT",)),
])
def test_a_licence_spelling_inside_another_word_is_not_a_mention(prose, names):
    assert checker.names_the_licence(prose, names) == []


def test_several_licences_can_be_mentioned_at_once():
    found = checker.names_the_licence("MIT in one place, GPL-2.0 in another",
                                      ("MIT", "GPL-2.0"))

    assert found == ["MIT", "GPL-2.0"]


# ---------------------------------------------------------------------------
# The repository as it stands
# ---------------------------------------------------------------------------

def test_this_repository_is_self_consistent(capsys):
    """The end-to-end check, on the real files.

    It passes today with GPL-2.0-only, and it is the thing that will have to pass
    after the relicensing commit -- which is the point of writing it now, while
    there is nothing to fix in a hurry.
    """
    assert checker.main() == 0
    assert "PASSED" in capsys.readouterr().out
