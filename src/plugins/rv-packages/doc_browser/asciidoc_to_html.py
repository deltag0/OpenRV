#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Python port of the ``asciidoc_to_html`` Mu module from ``doc_browser``."""

from __future__ import annotations

import re

_LISTING_RE = re.compile(r"^-+$")
_EXAMPLE_RE = re.compile(r"^=+$")
_BULLET_RE = re.compile(r"^ *(- |\*+ )")
_ENUM_RE = re.compile(r"^([a-zA-Z]\.|[0-9]+\.|\.\.+)")
_TABLE_BOUNDS_RE = re.compile(r"^[|]=+$")
_TABLE_ROW_RE = re.compile(r"^[|][^=]")
_ATTR_RE = re.compile(r"^\[.*\]$")
_URL_RE = re.compile(r"^(https?|file):.*$")


def formatting(text: str) -> str:
    """Convert inline markup in ``text`` to HTML."""
    parts: list[str] = []
    for word in text.split(" "):
        if not word:
            continue

        startbold = word[0] == "*"
        endbold = word[-1] == "*"
        startemph = word[0] == "_"
        endemph = word[-1] == "_"
        startemph2 = word[0] == "'"
        endemph2 = word[-1] == "'"
        startmono = word[0] == "+"
        endmono = word[-1] == "+"
        startpass = word[0] == "`"
        endpass = word[-1] == "`"

        if startbold and not endbold:
            parts.append(f" <b>{word[1:]}")
        elif startbold and endbold:
            parts.append(f" <b>{word[1:-1]}</b>")
        elif endbold:
            parts.append(f" {word[:-1]}</b>")

        elif startemph and not endemph:
            parts.append(f" <i>{word[1:]}")
        elif startemph and endemph:
            parts.append(f" <i>{word[1:-1]}</i>")
        elif endemph:
            parts.append(f" {word[:-1]}</i>")

        elif startemph2 and not endemph2:
            parts.append(f" <i>{word[1:]}")
        elif startemph2 and endemph2:
            parts.append(f" <i>{word[1:-1]}</i>")
        elif endemph2:
            parts.append(f" {word[:-1]}</i>")

        elif startmono and not endmono:
            parts.append(f" <tt>{word[1:]}")
        elif startmono and endmono:
            parts.append(f" <tt>{word[1:-1]}</tt>")
        elif endmono:
            parts.append(f" {word[:-1]}</tt>")

        elif startpass and not endpass:
            parts.append(f" <tt>{word[1:]}")
        elif startpass and endpass:
            parts.append(f" <tt>{word[1:-1]}</tt>")
        elif endpass:
            parts.append(f" {word[:-1]}</tt>")

        elif _URL_RE.match(word):
            parts.append(f' <a href="{word}">{word}</a>')
        else:
            parts.append(f" {word}")

    return "".join(parts)


def toHTML(text: str) -> str:
    """Convert asciidoc-ish markup in ``text`` to HTML."""
    lines = text.split("\n")
    out: list[str] = []
    inpre = False
    inp = False
    intable = False
    inlist = False
    attrs: list[tuple[str, str]] = []

    for line in lines:
        islisting = bool(_LISTING_RE.match(line))
        isexample = bool(_EXAMPLE_RE.match(line))
        istable = bool(_TABLE_BOUNDS_RE.match(line))
        isrow = bool(_TABLE_ROW_RE.match(line))
        isbullet = bool(_BULLET_RE.match(line))
        isattr = bool(_ATTR_RE.match(line))

        if inlist and not isbullet:
            out.append("</ul>\n")
            inlist = False

        if line == "" and not inpre:
            out.append("</p>" if inp else "<p>")
            inp = not inp
            attrs.clear()
        elif isattr:
            try:
                inner = line[1:-1]
                attrs.clear()
                for pair in inner.split('",'):
                    name, value = pair.split("=", 1)
                    value = value.split('"')[1]
                    attrs.append((name, value))
            except (IndexError, ValueError):
                pass
        elif isbullet:
            if not inlist:
                out.append("<ul>")
            inlist = True
            out.append(f"<li> {formatting(line)} </li>\n")
        elif islisting or isexample:
            if inpre:
                out.append("</pre>")
                inpre = False
            else:
                if inp:
                    out.append("</p>")
                    inp = False
                tclass = "listing" if line.startswith("-") else "example"
                out.append(f'<pre class="{tclass}">')
                inpre = True
            attrs.clear()
        elif istable:
            if intable:
                out.append("</table>")
            else:
                tclass = "basictable"
                attrlist = ""
                for name, value in attrs:
                    if name == "width":
                        attrlist += f" width={value}"
                    elif name == "class":
                        tclass = value
                out.append(f'<table class="{tclass}" {attrlist}>')
            intable = not intable
            attrs.clear()
        elif intable and isrow:
            out.append('<tr class="basictr">')
            cells = line.split("|")[1:]
            for cell in cells:
                out.append('<td class="basictd">')
                out.append(cell)
                out.append("</td>")
            out.append("</tr>")
            attrs.clear()
        else:
            out.append(formatting(line) + "\n")
            attrs.clear()

    return "".join(out)
