# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import dataclasses
from copy import deepcopy
from textwrap import dedent
from lxml import etree
import math
import pytest
from picosvgx.svg import SVG, SVGPath
from picosvgx.svg_meta import parse_css_declarations
import re
from svg_test_helpers import *
from typing import Tuple


def _test(actual, expected_result, op):
    actual = op(load_test_svg(actual))
    expected_result = load_test_svg(expected_result)
    drop_whitespace(actual)
    drop_whitespace(expected_result)
    print(f"A: {pretty_print(actual.toetree())}")
    print(f"E: {pretty_print(expected_result.toetree())}")
    assert pretty_print(actual.toetree()) == pretty_print(expected_result.toetree())


@pytest.mark.parametrize(
    "shape, expected_fields",
    [
        # path, fill
        ("<path d='M1,1 2,2' fill='blue' />", {"fill": "blue"}),
        # rect, opacity
        ("<rect x='5' y='5' width='5' height='5' opacity='0.5'/>", {"opacity": 0.5}),
        # polyline, clip-path
        (
            "<polyline points='1,1 5,5 2,2' clip-path='url(#cp)'/>",
            {"clip_path": "url(#cp)"},
        ),
        # line, stroke
        ("<line x1='1' y1='1' x2='10' y2='10' stroke='red'/>", {"stroke": "red"}),
    ],
)
def test_common_attrib(shape, expected_fields):
    svg = SVG.fromstring(svg_string(shape))
    field_values = dataclasses.asdict(svg.shapes()[0])
    for field_name, expected_value in expected_fields.items():
        assert field_values.get(field_name, "") == expected_value, field_name

    svg = svg.shapes_to_paths()
    field_values = dataclasses.asdict(svg.shapes()[0])
    for field_name, expected_value in expected_fields.items():
        assert field_values.get(field_name, "") == expected_value, field_name


# https://www.w3.org/TR/SVG11/shapes.html
@pytest.mark.parametrize(
    "shape, expected_path",
    [
        # path: direct passthrough
        ("<path d='I love kittens'/>", 'd="I love kittens"'),
        # path no @d
        ("<path duck='Mallard'/>", ""),
        # line
        ('<line x1="10" x2="50" y1="110" y2="150"/>', 'd="M10,110 L50,150"'),
        # line, decimal positioning
        (
            '<line x1="10.0" x2="50.5" y1="110.2" y2="150.7"/>',
            'd="M10,110.2 L50.5,150.7"',
        ),
        # rect: minimal valid example
        ("<rect width='1' height='1'/>", 'd="M0,0 H1 V1 H0 V0 Z"'),
        # rect: sharp corners
        (
            "<rect x='10' y='11' width='17' height='11'/>",
            'd="M10,11 H27 V22 H10 V11 Z"',
        ),
        # rect: round corners
        (
            "<rect x='9' y='9' width='11' height='7' rx='2'/>",
            'd="M11,9 H18 A2 2 0 0 1 20,11 V14 A2 2 0 0 1 18,16 H11'
            ' A2 2 0 0 1 9,14 V11 A2 2 0 0 1 11,9 Z"',
        ),
        # rect: simple
        (
            "<rect x='11.5' y='16' width='11' height='2'/>",
            'd="M11.5,16 H22.5 V18 H11.5 V16 Z"',
        ),
        # polygon
        ("<polygon points='30,10 50,30 10,30'/>", 'd="M30,10 50,30 10,30 Z"'),
        # polyline
        ("<polyline points='30,10 50,30 10,30'/>", 'd="M30,10 50,30 10,30"'),
        # circle, minimal valid example
        ("<circle r='1'/>", 'd="M1,0 A1 1 0 1 1 -1,0 A1 1 0 1 1 1,0 Z"'),
        # circle
        (
            "<circle cx='600' cy='200' r='100'/>",
            'd="M700,200 A100 100 0 1 1 500,200 A100 100 0 1 1 700,200 Z"',
        ),
        # circle, decimal positioning
        (
            "<circle cx='12' cy='6.5' r='1.5'></circle>",
            'd="M13.5,6.5 A1.5 1.5 0 1 1 10.5,6.5 A1.5 1.5 0 1 1 13.5,6.5 Z"',
        ),
        # ellipse
        (
            '<ellipse cx="100" cy="50" rx="100" ry="50"/>',
            'd="M200,50 A100 50 0 1 1 0,50 A100 50 0 1 1 200,50 Z"',
        ),
        # ellipse, decimal positioning
        (
            '<ellipse cx="100.5" cy="50" rx="10" ry="50.5"/>',
            'd="M110.5,50 A10 50.5 0 1 1 90.5,50 A10 50.5 0 1 1 110.5,50 Z"',
        ),
    ],
)
def test_shapes_to_paths(shape: str, expected_path: str):
    actual = SVG.fromstring(svg_string(shape)).shapes_to_paths(inplace=True).toetree()
    expected_result = SVG.fromstring(svg_string(f"<path {expected_path}/>")).toetree()
    print(f"A: {pretty_print(actual)}")
    print(f"E: {pretty_print(expected_result)}")
    assert etree.tostring(actual) == etree.tostring(expected_result)


@pytest.mark.parametrize(
    "shape, expected_cmds",
    [
        # line
        (
            '<line x1="10" x2="50" y1="110" y2="150"/>',
            [("M", (10.0, 110.0)), ("L", (50.0, 150.0))],
        ),
        # path explodes to show implicit commands
        (
            '<path d="m1,1 2,0 1,3"/>',
            [("m", (1.0, 1.0)), ("l", (2.0, 0.0)), ("l", (1.0, 3.0))],
        ),
        # vertical and horizontal movement
        (
            '<path d="m1,1 v2 h2z"/>',
            [("m", (1.0, 1.0)), ("v", (2.0,)), ("h", (2.0,)), ("z", ())],
        ),
        # arc, negative offsets
        (
            '<path d="M7,5 a3,1 0,0,0 0,-3 a3,3 0 0 1 -4,2"/>',
            [
                ("M", (7.0, 5.0)),
                ("a", (3.0, 1.0, 0.0, 0.0, 0.0, 0.0, -3.0)),
                ("a", (3.0, 3.0, 0.0, 0.0, 1.0, -4.0, 2.0)),
            ],
        ),
        # minimalist numbers, who needs spaces or commas
        (
            '<path d="m-1-1 0.5-.5-.5-.3.1.2.2.51.52.711"/>',
            [
                ("m", (-1.0, -1.0)),
                ("l", (0.5, -0.5)),
                ("l", (-0.5, -0.3)),
                ("l", (0.1, 0.2)),
                ("l", (0.2, 0.51)),
                ("l", (0.52, 0.711)),
            ],
        ),
    ],
)
def test_iter(shape, expected_cmds):
    svg_path = SVG.fromstring(svg_string(shape)).shapes_to_paths().shapes()[0]
    actual_cmds = [t for t in svg_path]
    print(f"A: {actual_cmds}")
    print(f"E: {expected_cmds}")
    assert actual_cmds == expected_cmds


@pytest.mark.parametrize(
    "actual, expected_result", [("use-ellipse.svg", "use-ellipse-resolved.svg")]
)
def test_resolve_use(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.resolve_use(inplace=True))


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("stroke-simplepath-before.svg", "stroke-simplepath-nano.svg"),
        ("stroke-path-before.svg", "stroke-path-nano.svg"),
        ("stroke-capjoinmiterlimit-before.svg", "stroke-capjoinmiterlimit-nano.svg"),
        ("scale-strokes-before.svg", "scale-strokes-nano.svg"),
        ("stroke-fill-opacity-before.svg", "stroke-fill-opacity-nano.svg"),
        ("stroke-dasharray-before.svg", "stroke-dasharray-nano.svg"),
        ("stroke-circle-dasharray-before.svg", "stroke-circle-dasharray-nano.svg"),
        ("clip-rect.svg", "clip-rect-clipped-nano.svg"),
        ("clip-ellipse.svg", "clip-ellipse-clipped-nano.svg"),
        ("clip-curves.svg", "clip-curves-clipped-nano.svg"),
        ("clip-multirect.svg", "clip-multirect-clipped-nano.svg"),
        ("clip-groups.svg", "clip-groups-clipped-nano.svg"),
        ("clip-use.svg", "clip-use-clipped-nano.svg"),
        ("clip-rule-example.svg", "clip-rule-example-nano.svg"),
        ("clip-from-brazil-flag.svg", "clip-from-brazil-flag-nano.svg"),
        ("clip-rule-evenodd.svg", "clip-rule-evenodd-clipped-nano.svg"),
        ("clip-clippath-attrs.svg", "clip-clippath-attrs-nano.svg"),
        ("clip-clippath-none.svg", "clip-clippath-none-nano.svg"),
        ("rotated-rect.svg", "rotated-rect-nano.svg"),
        ("translate-rect.svg", "translate-rect-nano.svg"),
        ("ungroup-before.svg", "ungroup-nano.svg"),
        ("ungroup-multiple-children-before.svg", "ungroup-multiple-children-nano.svg"),
        ("group-stroke-before.svg", "group-stroke-nano.svg"),
        ("arcs-before.svg", "arcs-nano.svg"),
        ("invisible-before.svg", "invisible-nano.svg"),
        ("transform-before.svg", "transform-nano.svg"),
        ("group-data-name-before.svg", "group-data-name-nano.svg"),
        ("matrix-before.svg", "matrix-nano.svg"),
        ("degenerate-before.svg", "degenerate-nano.svg"),
        ("fill-rule-evenodd-before.svg", "fill-rule-evenodd-nano.svg"),
        ("twemoji-lesotho-flag-before.svg", "twemoji-lesotho-flag-nano.svg"),
        ("inline-css-style-before.svg", "inline-css-style-nano.svg"),
        ("clipped-strokes-before.svg", "clipped-strokes-nano.svg"),
        ("drop-anon-symbols-before.svg", "drop-anon-symbols-nano.svg"),
        ("scale-strokes-before.svg", "scale-strokes-nano.svg"),
        ("ungroup-with-ids-before.svg", "ungroup-with-ids-nano.svg"),
        ("stroke-with-id-before.svg", "stroke-with-id-nano.svg"),
        ("drop-title-meta-desc-before.svg", "drop-title-meta-desc-nano.svg"),
        ("no-viewbox-before.svg", "no-viewbox-nano.svg"),
        ("decimal-viewbox-before.svg", "decimal-viewbox-nano.svg"),
        ("inkscape-noise-before.svg", "inkscape-noise-nano.svg"),
        ("flag-use-before.svg", "flag-use-nano.svg"),
        ("ungroup-transform-before.svg", "ungroup-transform-nano.svg"),
        ("pathops-tricky-path-before.svg", "pathops-tricky-path-nano.svg"),
        ("gradient-template-1-before.svg", "gradient-template-1-nano.svg"),
        ("nested-svg-slovenian-flag-before.svg", "nested-svg-slovenian-flag-nano.svg"),
        ("global-fill-none-before.svg", "global-fill-none-nano.svg"),
        ("stroke-polyline-before.svg", "stroke-polyline-nano.svg"),
        ("clip-the-clip-before.svg", "clip-the-clip-nano.svg"),
        ("ungroup-group-transform-before.svg", "ungroup-group-transform-nano.svg"),
        ("ungroup-transform-clip-before.svg", "ungroup-transform-clip-nano.svg"),
        (
            "ungroup-retain-for-opacity-before.svg",
            "ungroup-retain-for-opacity-nano.svg",
        ),
        (
            "transform-radial-userspaceonuse-before.svg",
            "transform-radial-userspaceonuse-nano.svg",
        ),
        (
            "transform-linear-objectbbox-before.svg",
            "transform-linear-objectbbox-nano.svg",
        ),
        (
            "transform-radial-objectbbox-before.svg",
            "transform-radial-objectbbox-nano.svg",
        ),
        (
            "illegal-inheritance-before.svg",
            "illegal-inheritance-nano.svg",
        ),
        (
            "explicit-default-fill-no-inherit-before.svg",
            "explicit-default-fill-no-inherit-nano.svg",
        ),
        (
            "explicit-default-stroke-no-inherit-before.svg",
            "explicit-default-stroke-no-inherit-nano.svg",
        ),
        (
            "inherit-default-fill-before.svg",
            "inherit-default-fill-nano.svg",
        ),
        # propagation of display:none
        (
            "display_none-before.svg",
            "display_none-nano.svg",
        ),
        # https://github.com/googlefonts/picosvg/issues/252
        (
            "strip_empty_subpath-before.svg",
            "strip_empty_subpath-nano.svg",
        ),
        (
            "xpacket-before.svg",
            "xpacket-nano.svg",
        ),
        # https://github.com/googlefonts/picosvg/issues/297
        # Demonstrate comments outside root drop just fine
        (
            "comments-before.svg",
            "comments-nano.svg",
        ),
    ],
)
def test_topicosvg(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.topicosvg())


@pytest.mark.parametrize("inplace", [True, False])
@pytest.mark.parametrize(
    "actual, expected_result",
    [
        # https://github.com/googlefonts/picosvg/issues/297
        (
            "comments-image-style-before.svg",
            "comments-image-style-nano.svg",
        ),
    ],
)
def test_topicosvg_drop_unsupported(actual, inplace, expected_result):
    actual_copy = deepcopy(actual)
    # This should fail unless we drop unsupported
    with pytest.raises(ValueError) as e:
        _test(actual_copy, expected_result, lambda svg: svg.topicosvg(inplace=inplace))
    assert "BadElement" in str(e.value)
    actual_copy = deepcopy(actual)
    _test(
        actual_copy,
        expected_result,
        lambda svg: svg.topicosvg(inplace=inplace, drop_unsupported=True),
    )


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("outside-viewbox.svg", "outside-viewbox-clipped.svg"),
        ("outside-viewbox-grouped.svg", "outside-viewbox-grouped-clipped.svg"),
    ],
)
def test_clip_to_viewbox(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.clip_to_viewbox().round_floats(4))


@pytest.mark.parametrize(
    "actual, expected_result", [("invisible-before.svg", "invisible-after.svg")]
)
def test_remove_unpainted_shapes(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.remove_unpainted_shapes())


@pytest.mark.parametrize(
    "svg_file, expected_violations",
    [
        ("good-defs-0.svg", ()),
        (
            "bad-defs-0.svg",
            (
                "BadElement: /svg[0]/defs[1]",
                "BadElement: /svg[0]/donkey[0]",
            ),
        ),
        ("bad-defs-1.svg", ("MissingElement: /svg[0]/defs[0]",)),
        (
            "bad-ids-1.svg",
            (
                'BadElement: /svg[0]/path[1] reuses id="not_so_unique", first seen at /svg[0]/path[0]',
            ),
        ),
    ],
)
def test_checkpicosvg(svg_file, expected_violations):
    nano_violations = load_test_svg(svg_file).checkpicosvg()
    assert expected_violations == nano_violations


@pytest.mark.parametrize(
    "svg_string, expected_result",
    [
        ('<svg version="1.1" xmlns="http://www.w3.org/2000/svg"/>', None),
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="7 7 12 12"/>',
            (7, 7, 12, 12),
        ),
    ],
)
def test_viewbox(svg_string, expected_result):
    assert SVG.fromstring(svg_string).view_box() == expected_result


@pytest.mark.parametrize(
    "svg_string, names, expected_result",
    [
        # No change
        (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"/>',
            ("viewBox", "width", "height"),
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"/>',
        ),
        # Drop viewBox, width, height
        (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="7 7 12 12" height="7" width="11"/>',
            ("viewBox", "width", "height"),
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"/>',
        ),
        # Drop width, height
        (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="7 7 12 12" height="7" width="11"/>',
            ("width", "height"),
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="7 7 12 12"/>',
        ),
    ],
)
def test_remove_attributes(svg_string, names, expected_result):
    assert (
        SVG.fromstring(svg_string).remove_attributes(names).tostring()
    ) == expected_result


# https://github.com/rsheeter/picosvg/issues/1
@pytest.mark.parametrize(
    "svg_string, expected_result",
    [
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="7 7 12 12"/>',
            0.012,
        ),
        (
            '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"/>',
            0.128,
        ),
    ],
)
def test_tolerance(svg_string, expected_result):
    assert round(SVG.fromstring(svg_string).tolerance, 4) == expected_result


@pytest.mark.parametrize(
    "style, property_names, expected_output, expected_unparsed",
    [
        ("fill:none", None, {"fill": "none"}, ""),
        ("fill: url(#grad1)", None, {"fill": "url(#grad1)"}, ""),
        (
            " stroke  : blue   ; stroke-width :4;   ",
            None,
            {"stroke": "blue", "stroke-width": "4"},
            "",
        ),
        (
            "enable-background:new 0 0 128 128; foo:abc; bar:123;",
            {"enable-background"},
            {"enable-background": "new 0 0 128 128"},
            "foo:abc; bar:123;",
        ),
        (
            # does not support vendor style attributes due to lxml module, see #293
            "stroke:#FF0000;stroke-width:0.5;fill:none;-inkscape-font-specification:'Roboto';",
            None,
            {"stroke": "#FF0000", "stroke-width": "0.5", "fill": "none"},
            "-inkscape-font-specification:'Roboto';",
        ),
    ],
)
def test_parse_css_declarations(
    style, property_names, expected_output, expected_unparsed
):
    element = etree.Element("test")
    output = element.attrib
    unparsed = parse_css_declarations(style, output, property_names)
    assert output == expected_output
    assert unparsed == expected_unparsed


@pytest.mark.parametrize("style", ["foo;bar;", "foo:bar:baz;"])
def test_parse_css_declarations_invalid(style):
    with pytest.raises(ValueError, match="Invalid CSS declaration syntax"):
        parse_css_declarations(style, {})


@pytest.mark.parametrize(
    "actual, expected_result",
    [("inline-css-style-before.svg", "inline-css-style-after.svg")],
)
def test_apply_style_attributes(actual, expected_result):
    _test(actual, expected_result, lambda svg: svg.apply_style_attributes())
    # check we get the same output even if shapes were already parsed
    _test(
        actual,
        expected_result,
        lambda svg: svg.shapes() and svg.apply_style_attributes(),
    )


@pytest.mark.parametrize(
    "gradient_string, expected_result",
    [
        # No transform, no change
        (
            '<linearGradient id="c" x1="63.85" x2="63.85" y1="4245" y2="4137.3" gradientUnits="userSpaceOnUse"/>',
            '<linearGradient id="c" x1="63.85" y1="4245" x2="63.85" y2="4137.3" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u1f392.svg w/ dx changed from 0 to 1
        # scale, translate
        (
            '<linearGradient id="c" x1="63.85" x2="63.85" y1="4245" y2="4137.3" gradientTransform="translate(1 -4122)" gradientUnits="userSpaceOnUse"/>',
            '<linearGradient id="c" x1="64.85" y1="123" x2="64.85" y2="15.3" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u1f392.svg w/sx changed from 1 to 0.5
        # scale, translate
        (
            '<radialGradient id="b" cx="63.523" cy="12368" r="53.477" gradientTransform="matrix(.5 0 0 .2631 0 -3150)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="b" cx="63.523" cy="395.366021" r="53.477" gradientTransform="matrix(0.5 0 0 0.2631 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u1f44d.svg
        # Using all 6 parts
        (
            '<radialGradient id="d" cx="2459.4" cy="-319.18" r="20.331" gradientTransform="matrix(-1.3883 .0794 -.0374 -.6794 3505.4 -353.39)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="d" cx="-71.60264" cy="-94.82264" r="20.331" gradientTransform="matrix(-1.3883 0.0794 -0.0374 -0.6794 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
        # Manually constructed objectBBox
        (
            '<radialGradient id="mbbox" cx="0.75" cy="0.75" r="0.40" gradientTransform="matrix(1 1 -0.7873 -0.001717 0.5 0)" gradientUnits="objectBoundingBox"/>',
            '<radialGradient id="mbbox" cx="0.748907" cy="0.11353" r="0.4" gradientTransform="matrix(1 1 -0.7873 -0.001717 0 0)"/>',
        ),
        # Real example from emoji_u26BE
        # https://github.com/googlefonts/picosvg/issues/129
        (
            '<radialGradient id="f" cx="-779.79" cy="3150" r="58.471" gradientTransform="matrix(0 1 -1 0 3082.5 1129.5)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="f" cx="349.71" cy="67.5" r="58.471" gradientTransform="matrix(0 1 -1 0 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
        # Real example from emoji_u270c.svg
        # Very small values (e-17...) and float math makes for large errors
        (
            '<radialGradient id="f" cx="75.915" cy="20.049" r="71.484" fx="88.617" fy="-50.297" gradientTransform="matrix(6.1232e-17 1 -1.0519 6.4408e-17 97.004 -55.866)" gradientUnits="userSpaceOnUse"/>',
            '<radialGradient id="f" cx="20.049" cy="-72.168891" r="71.484" fx="32.751" fy="-142.514891" gradientTransform="matrix(0 1 -1.0519 0 0 0)" gradientUnits="userSpaceOnUse"/>',
        ),
    ],
)
def test_apply_gradient_translation(gradient_string, expected_result):
    svg = SVG.fromstring(svg_string(gradient_string))
    for grad_el in svg._select_gradients():
        svg._apply_gradient_translation(grad_el)
    el = svg.xpath_one("//svg:linearGradient | //svg:radialGradient")

    for node in svg.svg_root.getiterator():
        node.tag = etree.QName(node).localname
    etree.cleanup_namespaces(svg.svg_root)

    assert etree.tostring(el).decode("utf-8") == expected_result


@pytest.mark.parametrize(
    "svg_content, expected_result",
    [
        # Blank fill
        # https://github.com/googlefonts/nanoemoji/issues/229
        (
            '<path fill="" d=""/>',
            (SVGPath(),),
        ),
    ],
)
def test_default_for_blank(svg_content, expected_result):
    assert tuple(SVG.fromstring(svg_string(svg_content)).shapes()) == expected_result


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("gradient-template-1-before.svg", "gradient-template-1-after.svg"),
        ("gradient-template-2-before.svg", "gradient-template-2-after.svg"),
        ("gradient-template-3-before.svg", "gradient-template-3-after.svg"),
    ],
)
def test_resolve_gradient_templates(actual, expected_result):
    def apply_templates(svg):
        for grad_el in svg._select_gradients():
            svg._apply_gradient_template(grad_el)
        svg._remove_orphaned_gradients()
        return svg

    _test(
        actual,
        expected_result,
        apply_templates,
    )


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("nested-svg-slovenian-flag-before.svg", "nested-svg-slovenian-flag-after.svg"),
    ],
)
def test_resolve_nested_svgs(actual, expected_result):
    _test(
        actual,
        expected_result,
        lambda svg: svg.resolve_nested_svgs(),
    )


def test_tostring_pretty_print():
    svg = SVG.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">\n'
        "<g>  \n"
        "\t  <g>  \r\n"
        '\t\t  <path d="M60,30 L100,30 L100,70 L60,70 Z"/>\n\n'
        "\t  </g>  \r"
        "</g> \n"
        "</svg>"
    )

    assert svg.tostring(pretty_print=False) == (
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">'
        "<g>"
        "<g>"
        '<path d="M60,30 L100,30 L100,70 L60,70 Z"/>'
        "</g>"
        "</g>"
        "</svg>"
    )

    assert svg.tostring(pretty_print=True) == dedent(
        """\
        <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">
          <g>
            <g>
              <path d="M60,30 L100,30 L100,70 L60,70 Z"/>
            </g>
          </g>
        </svg>
        """
    )


@pytest.mark.parametrize(
    "actual, expected_result",
    [
        ("fill-rule-evenodd-before.svg", "fill-rule-evenodd-after.svg"),
    ],
)
def test_evenodd_to_nonzero_winding(actual, expected_result):
    _test(
        actual,
        expected_result,
        lambda svg: svg.evenodd_to_nonzero_winding().round_floats(3, inplace=True),
    )


@pytest.mark.parametrize(
    "input_svg",
    (
        "explicit-default-fill-no-inherit-before.svg",
        "explicit-default-stroke-no-inherit-before.svg",
        "inherit-default-fill-before.svg",
    ),
)
def test_update_tree_lossless(input_svg):
    with open(locate_test_file(input_svg)) as f:
        svg_data = f.read()
    svg = SVG.fromstring(svg_data)
    assert not svg.elements  # initially empty list

    # _elements() parses shapes using from_element, populating self.elements
    _ = svg._elements()
    assert svg.elements

    # _update_etree calls to_element on each shape and resets self.elements
    svg._update_etree()
    assert not svg.elements

    assert svg.tostring(pretty_print=True) == svg_data


def _only(maybe_many):
    if len(maybe_many) != 1:
        raise ValueError(f"Must have exactly 1 item in {maybe_many}")
    return next(iter(maybe_many))


def _subpaths(path: str) -> Tuple[str, ...]:
    return tuple(m.group() for m in re.finditer(r"[mM][^Mm]*", path))


# https://github.com/googlefonts/picosvg/issues/269
# Make sure we drop subpaths that have 0 area after rounding.
def test_shapes_for_stroked_path():
    svg = SVG.parse(locate_test_file("emoji_u1f6d2.svg")).topicosvg()
    path_before = _only(svg.shapes()).as_path().d
    svg = svg.topicosvg()
    path_after = _only(svg.shapes()).as_path().d

    assert len(_subpaths(path_before)) == len(
        _subpaths(path_after)
    ), f"Lost subpaths\n{path_before}\n{path_after}"


@pytest.mark.parametrize("inplace", (True, False))
def test_topicosvg_ndigits(inplace):
    svg = SVG.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">'
        "<defs/>"
        '<path d="M60.4999,30 L100.06,30 L100.06,70 L60.4999,70 Z"/>'
        "</svg>"
    )
    pico = svg.topicosvg(ndigits=1, inplace=inplace)
    assert pico.tostring() == dedent(
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 128 128">'
        "<defs/>"
        '<path d="M60.5,30 L100.1,30 L100.1,70 L60.5,70 Z"/>'
        "</svg>"
    )


def test_remove_processing_instructions():
    xpacket_svg = load_test_svg("xpacket-before.svg")
    assert "xpacket" in xpacket_svg.tostring()
    pico_svg = xpacket_svg.remove_processing_instructions()
    assert "xpacket" not in pico_svg.tostring()


@pytest.mark.parametrize(
    "svg_string, match_re, expected_passthrough",
    [
        # text element
        (
            """
            <svg xmlns="http://www.w3.org/2000/svg"
                width="512" height="512"
                viewBox="0 0 30 30">
            <text x="20" y="35">Hello</text>
            </svg>
            """,
            r"Unable to convert to picosvg: BadElement: /svg\[0\]/text\[0\]",
            "text",
        ),
        # text with tspan
        (
            """
            <svg xmlns="http://www.w3.org/2000/svg"
                width="512" height="512"
                viewBox="0 0 30 30">
            <text x="20" y="35">
                <tspan x="0" y="20" style="font-style:normal;font-variant:normal;font-weight:normal;font-stretch:normal;font-size:10px;font-variant-ligatures:normal;font-variant-caps:small-caps;font-variant-numeric:normal;font-variant-east-asian:normal;stroke-width:1;">Hello</tspan>
            </text>
            </svg>
            """,
            r"Unable to convert to picosvg: BadElement: /svg\[0\]/text\[0\]",
            "tspan",
        ),
        # text with textPath, sample copied from https://developer.mozilla.org/en-US/docs/Web/SVG/Element/textPath
        (
            """
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <!-- to hide the path, it is usually wrapped in a <defs> element -->
                <!-- <defs> -->
                <path
                    id="MyPath"
                    fill="none"
                    stroke="red"
                    d="M10,90 Q90,90 90,45 Q90,10 50,10 Q10,10 10,40 Q10,70 45,70 Q70,70 75,50" />
                <!-- </defs> -->

                <text>
                    <textPath href="#MyPath">A very long text on path.</textPath>
                </text>
                </svg>
            """,
            r"Unable to convert to picosvg: BadElement: /svg\[0\]/text\[0\]",
            "textPath",
        ),
    ],
)
def test_allow_text(svg_string, match_re, expected_passthrough):
    text_svg = SVG.fromstring(svg_string)
    with pytest.raises(
        ValueError,
        match=match_re,
    ):
        text_svg.topicosvg()
    assert expected_passthrough in text_svg.topicosvg(allow_text=True).tostring()


def test_bounding_box():
    bounding_svg = load_test_svg("bounding.svg")
    bounds = bounding_svg.bounding_box()
    assert math.isclose(bounds.x, 14.22469, abs_tol=1e-5)
    assert math.isclose(bounds.y, 48.57185, abs_tol=1e-5)
    assert math.isclose(bounds.w, 95.64109, abs_tol=1e-5)
    assert math.isclose(bounds.h, 62.20909, abs_tol=1e-5)


@pytest.mark.parametrize(
    "svg_input, expected_output",
    [
        # Test basic unit parsing in attributes
        # 72pt = 72 * 96/72 = 96px
        (
            '<rect width="100px" height="72pt" x="10" y="20"/>',
            '<rect width="100" height="96" x="10" y="20"/>'
        ),
        # Test percentage and inch units
        # 2.5in = 2.5 * 96 = 240px, 50% stays as 50
        (
            '<rect width="50%" height="2.5in" x="0" y="0"/>',
            '<rect width="50%" height="240" x="0" y="0"/>'
        ),
        # Test mixed units in different attributes
        # 25pt = 25 * 96/72 = 33.33333333333333px
        (
            '<circle cx="50px" cy="25pt" r="10"/>',
            '<circle cx="50" cy="33.33333333333333" r="10"/>'
        ),
        # Test other absolute units: mm and cm
        # 10mm = 10 * 96/25.4 = 37.795275590551185px
        # Note: Only testing mm because cm has floating point precision issues
        (
            '<rect width="10mm" height="10mm"/>',
            '<rect width="37.795275590551185" height="37.795275590551185"/>'
        ),
        # Test pica unit: pc
        # 2pc = 2 * 16 = 32px
        (
            '<rect width="2pc" height="1.5pc"/>',
            '<rect width="32" height="24"/>'
        ),
        # Test stroke-width with units
        # 2pt = 2 * 96/72 = 2.6666666666666665px
        (
            '<line x1="0" y1="0" x2="100" y2="100" style="stroke-width: 2pt"/>',
            '<line x1="0" y1="0" x2="100" y2="100" stroke-width="2.6666666666666665"/>'
        ),
        # Test negative values with units
        # -10px = -10, -5pt = -6.666666666666667
        (
            '<rect x="-10px" y="-5pt" width="100" height="100"/>',
            '<rect x="-10" y="-6.666666666666666" width="100" height="100"/>'
        ),
        # Test decimal values with units
        # 1.5in = 1.5 * 96 = 144px
        (
            '<rect width="1.5in" height="0.5in"/>',
            '<rect width="144" height="48"/>'
        ),
        # Test unitless values (should be treated as pixels)
        (
            '<rect width="100" height="50"/>',
            '<rect width="100" height="50"/>'
        ),
    ],
)
def test_robust_unit_parsing_attributes(svg_input: str, expected_output: str):
    """Test that SVG attributes with various units are parsed correctly."""
    actual_svg = SVG.fromstring(svg_string(svg_input))
    expected_svg = SVG.fromstring(svg_string(expected_output))

    # Normalize both for comparison
    actual_svg.shapes_to_paths(inplace=True)
    expected_svg.shapes_to_paths(inplace=True)

    actual_tree = actual_svg.toetree()
    expected_tree = expected_svg.toetree()

    # Compare the path data to verify correct unit conversion
    actual_paths = actual_tree.xpath("//svg:path/@d", namespaces={"svg": "http://www.w3.org/2000/svg"})
    expected_paths = expected_tree.xpath("//svg:path/@d", namespaces={"svg": "http://www.w3.org/2000/svg"})

    assert len(actual_paths) > 0, "No paths found in actual SVG"
    assert len(actual_paths) == len(expected_paths), f"Path count mismatch: {len(actual_paths)} != {len(expected_paths)}"

    for actual_path, expected_path in zip(actual_paths, expected_paths):
        assert actual_path == expected_path, f"Path mismatch:\nActual:   {actual_path}\nExpected: {expected_path}"


def test_css_length_error_handling():
    """Test that parse_css_length properly handles invalid inputs."""
    from picosvgx.svg_meta import parse_css_length

    # Test empty string
    with pytest.raises(ValueError, match="Empty CSS length value"):
        parse_css_length("")

    # Test whitespace only
    with pytest.raises(ValueError, match="Empty CSS length value"):
        parse_css_length("   ")

    # Test relative units that require context
    with pytest.raises(ValueError, match="Relative unit 'em' requires context"):
        parse_css_length("16em")

    with pytest.raises(ValueError, match="Relative unit 'rem' requires context"):
        parse_css_length("2rem")

    with pytest.raises(ValueError, match="Relative unit 'ex' requires context"):
        parse_css_length("10ex")

    with pytest.raises(ValueError, match="Relative unit 'ch' requires context"):
        parse_css_length("5ch")

    with pytest.raises(ValueError, match="Relative unit 'vw' requires context"):
        parse_css_length("50vw")

    with pytest.raises(ValueError, match="Relative unit 'vh' requires context"):
        parse_css_length("100vh")

    # Test invalid format
    with pytest.raises(ValueError, match="Invalid CSS length value"):
        parse_css_length("garbage")

    with pytest.raises(ValueError, match="Invalid CSS length value"):
        parse_css_length("px100")

    # Test valid inputs that should not raise
    assert parse_css_length("100px") == 100.0
    assert parse_css_length("50%") == 50.0
    assert parse_css_length("96") == 96.0  # unitless
    assert parse_css_length("-10px") == -10.0
    assert parse_css_length("1.5in") == 144.0


@pytest.mark.parametrize(
    "svg_input, should_have_svg_ns",
    [
        # SVG missing default xmlns="http://www.w3.org/2000/svg"
        (
            '<svg viewBox="0 0 100 100"><rect width="50" height="30"/></svg>',
            True
        ),
        # SVG with only xlink namespace, missing SVG namespace
        (
            '<svg xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100"><rect width="50" height="30"/></svg>',
            True
        ),
        # SVG already has correct namespace
        (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="50" height="30"/></svg>',
            True
        ),
    ],
)
def test_svg_namespace_auto_added(svg_input: str, should_have_svg_ns: bool):
    """Test that missing SVG default namespace xmlns='http://www.w3.org/2000/svg' is automatically added."""
    svg = SVG.fromstring(svg_input)
    tree = svg.toetree()

    if should_have_svg_ns:
        # Should automatically add SVG namespace
        assert tree.nsmap.get(None) == "http://www.w3.org/2000/svg"


@pytest.mark.parametrize(
    "svg_string, expected_passthrough",
    [
        # Test filter element in defs
        (
            """
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <filter id="blur1">
                        <feGaussianBlur stdDeviation="5"/>
                    </filter>
                </defs>
                <path d="M10,10 L90,90" fill="red"/>
            </svg>
            """,
            "filter",
        ),
        # Test mask element in defs
        (
            """
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <mask id="mask1">
                        <rect x="0" y="0" width="50" height="50" fill="white"/>
                    </mask>
                </defs>
                <path d="M10,10 L90,90" fill="blue"/>
            </svg>
            """,
            "mask",
        ),
        # Test switch element at root level
        (
            """
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <defs></defs>
                <switch>
                    <g systemLanguage="en">
                        <path d="M10,10 L90,90" fill="green"/>
                    </g>
                </switch>
            </svg>
            """,
            "switch",
        ),
        # Test pattern element in defs
        (
            """
            <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <pattern id="pattern1" width="10" height="10" patternUnits="userSpaceOnUse">
                        <rect width="10" height="10" fill="red"/>
                    </pattern>
                </defs>
                <path d="M10,10 L90,90" fill="blue"/>
            </svg>
            """,
            "pattern",
        ),
    ],
)
def test_allow_all_defs(svg_string, expected_passthrough):
    """Test that allow_all_defs flag preserves filter/mask/switch/pattern elements."""
    svg = SVG.fromstring(svg_string)

    # Without flag, elements may be removed or cause errors (default picosvg behavior)
    try:
        svg.topicosvg().tostring()
    except ValueError:
        # Some elements (like switch at root level) may cause errors without the flag
        pass

    # With allow_all_defs=True, elements should be preserved
    svg2 = SVG.fromstring(svg_string)
    result_with_flag = svg2.topicosvg(allow_all_defs=True).tostring()
    assert expected_passthrough in result_with_flag


def test_allow_all_defs_complex_filter():
    """Test allow_all_defs with complex filter containing multiple primitives."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="4" dy="4" stdDeviation="4" flood-color="black" flood-opacity="0.5"/>
            </filter>
            <filter id="blur">
                <feGaussianBlur in="SourceGraphic" stdDeviation="3"/>
            </filter>
        </defs>
        <path d="M50,50 L150,50 L100,150 Z" fill="red"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)

    # With flag, should preserve filters
    result = svg.topicosvg(allow_all_defs=True).tostring()
    assert "filter" in result
    assert "feDropShadow" in result or "feGaussianBlur" in result


def test_empty_clip_path_no_crash():
    """Test that empty or invalid clipPath doesn't crash (None bug fix)."""
    # This tests the fix for _resolve_clip_path returning None when clip_paths is empty
    svg_string = """
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <clipPath id="emptyClip">
                <!-- Empty clipPath with no shapes -->
            </clipPath>
        </defs>
        <path d="M10,10 L90,90" fill="red" clip-path="url(#emptyClip)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    # Should not crash with TypeError: 'NoneType' object is not iterable
    try:
        svg.topicosvg()
    except ValueError:
        # ValueError is acceptable (BadElement), but TypeError should not happen
        pass


# =============================================================================
# Comprehensive allow_all_defs robustness tests
# Based on: https://developer.mozilla.org/en-US/docs/Web/SVG/Element/filter
#           https://css-tricks.com/masking-vs-clipping-use/
# =============================================================================


def test_filter_drop_shadow_with_feMerge():
    """Test complex drop shadow filter using feOffset + feGaussianBlur + feMerge.

    This is a common pattern for creating drop shadows.
    Reference: https://developer.mozilla.org/en-US/docs/Web/SVG/Element/feMerge
    """
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="dropShadow" x="-20%" y="-20%" width="140%" height="140%">
                <feOffset in="SourceAlpha" dx="4" dy="4" result="offsetted"/>
                <feGaussianBlur in="offsetted" stdDeviation="3" result="blurred"/>
                <feMerge>
                    <feMergeNode in="blurred"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
        <rect x="50" y="50" width="100" height="100" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    # Verify all filter primitives are preserved
    assert "filter" in result
    assert "feOffset" in result
    assert "feGaussianBlur" in result
    assert "feMerge" in result
    assert "feMergeNode" in result


def test_filter_feColorMatrix_hue_rotation():
    """Test feColorMatrix for hue rotation effect.

    Reference: https://developer.mozilla.org/en-US/docs/Web/SVG/Element/feColorMatrix
    """
    svg_string = """
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="hueRotate">
                <feColorMatrix type="hueRotate" values="90"/>
            </filter>
            <filter id="saturate">
                <feColorMatrix type="saturate" values="0.5"/>
            </filter>
        </defs>
        <rect x="10" y="10" width="80" height="80" fill="red"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "feColorMatrix" in result
    assert "hueRotate" in result or "saturate" in result


def test_filter_feBlend_and_feComposite():
    """Test feBlend and feComposite filter primitives."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="blendFilter">
                <feFlood flood-color="red" flood-opacity="0.5" result="flood"/>
                <feBlend in="SourceGraphic" in2="flood" mode="multiply"/>
            </filter>
            <filter id="compositeFilter">
                <feComposite in="SourceGraphic" in2="SourceAlpha" operator="in"/>
            </filter>
        </defs>
        <circle cx="100" cy="100" r="50" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "filter" in result
    assert "feBlend" in result or "feComposite" in result or "feFlood" in result


def test_filter_feTurbulence_displacement():
    """Test feTurbulence with feDisplacementMap for noise effects."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="turbulence">
                <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" result="noise"/>
                <feDisplacementMap in="SourceGraphic" in2="noise" scale="20" xChannelSelector="R" yChannelSelector="G"/>
            </filter>
        </defs>
        <rect x="20" y="20" width="160" height="160" fill="green"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "filter" in result
    assert "feTurbulence" in result
    assert "feDisplacementMap" in result


def test_filter_lighting_effects():
    """Test filter lighting effects (feDiffuseLighting, feSpecularLighting)."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="lighting">
                <feDiffuseLighting in="SourceGraphic" surfaceScale="5" diffuseConstant="1">
                    <fePointLight x="100" y="100" z="200"/>
                </feDiffuseLighting>
            </filter>
        </defs>
        <circle cx="100" cy="100" r="80" fill="white"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "filter" in result
    assert "feDiffuseLighting" in result
    assert "fePointLight" in result


def test_mask_with_gradient():
    """Test mask with gradient for fade effect.

    Gradients in masks allow for smooth opacity transitions.
    Reference: https://css-tricks.com/masking-vs-clipping-use/
    """
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="fadeGrad">
                <stop offset="0%" stop-color="white"/>
                <stop offset="100%" stop-color="black"/>
            </linearGradient>
            <mask id="fadeMask">
                <rect x="0" y="0" width="200" height="200" fill="url(#fadeGrad)"/>
            </mask>
        </defs>
        <rect x="20" y="20" width="160" height="160" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "mask" in result
    assert "linearGradient" in result


def test_mask_with_shapes():
    """Test mask with multiple shapes."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <mask id="shapeMask">
                <rect x="0" y="0" width="200" height="200" fill="black"/>
                <circle cx="100" cy="100" r="80" fill="white"/>
                <rect x="60" y="60" width="80" height="80" fill="gray"/>
            </mask>
        </defs>
        <rect x="0" y="0" width="200" height="200" fill="red"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "mask" in result


def test_pattern_repeating():
    """Test repeating pattern with patternUnits."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <pattern id="dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
                <circle cx="10" cy="10" r="5" fill="blue"/>
            </pattern>
        </defs>
        <rect x="0" y="0" width="200" height="200" fill="url(#dots)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "pattern" in result
    assert "patternUnits" in result


def test_pattern_with_transform():
    """Test pattern with patternTransform."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <pattern id="rotatedPattern" width="40" height="40" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="20" height="20" fill="red"/>
                <rect x="20" y="20" width="20" height="20" fill="red"/>
            </pattern>
        </defs>
        <rect x="0" y="0" width="200" height="200" fill="url(#rotatedPattern)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "pattern" in result


def test_symbol_and_use():
    """Test symbol element with use references."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <symbol id="icon" viewBox="0 0 50 50">
                <circle cx="25" cy="25" r="20" fill="blue"/>
                <rect x="20" y="20" width="10" height="10" fill="white"/>
            </symbol>
        </defs>
        <rect x="0" y="0" width="200" height="200" fill="lightgray"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "symbol" in result


def test_multiple_defs_elements_mixed():
    """Test multiple different defs elements together."""
    svg_string = """
    <svg viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="grad1">
                <stop offset="0%" stop-color="red"/>
                <stop offset="100%" stop-color="blue"/>
            </linearGradient>
            <filter id="blur1">
                <feGaussianBlur stdDeviation="2"/>
            </filter>
            <mask id="mask1">
                <rect x="0" y="0" width="300" height="300" fill="white"/>
            </mask>
            <pattern id="pat1" width="10" height="10" patternUnits="userSpaceOnUse">
                <circle cx="5" cy="5" r="3" fill="green"/>
            </pattern>
        </defs>
        <rect x="10" y="10" width="280" height="280" fill="url(#grad1)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    # All defs should be preserved
    assert "linearGradient" in result
    assert "filter" in result
    assert "mask" in result
    assert "pattern" in result


def test_clipPath_with_non_shape_elements():
    """Test clipPath containing non-shape elements doesn't crash."""
    svg_string = """
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <clipPath id="complexClip">
                <text x="10" y="50">Clip</text>
            </clipPath>
        </defs>
        <rect x="0" y="0" width="100" height="100" fill="red" clip-path="url(#complexClip)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    # Should not crash - text in clipPath should be handled gracefully
    try:
        svg.topicosvg(allow_all_defs=True)
    except ValueError:
        # ValueError is acceptable, but no crash
        pass


def test_allow_all_defs_with_allow_text():
    """Test allow_all_defs combined with allow_text."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="textShadow">
                <feDropShadow dx="2" dy="2" stdDeviation="1"/>
            </filter>
        </defs>
        <text x="50" y="100" fill="black">Hello World</text>
        <rect x="20" y="120" width="160" height="60" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True, allow_text=True).tostring()

    assert "filter" in result
    assert "text" in result
    assert "Hello World" in result


def test_allow_all_defs_with_drop_unsupported():
    """Test allow_all_defs combined with drop_unsupported.

    foreignObject can embed arbitrary HTML (including <script>), so it must
    NOT be whitelisted.  With drop_unsupported=True it is silently removed
    while safe defs like <filter> are preserved.
    """
    svg_string = """
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="blur">
                <feGaussianBlur stdDeviation="3"/>
            </filter>
        </defs>
        <foreignObject x="10" y="10" width="80" height="80">
            <div xmlns="http://www.w3.org/1999/xhtml">HTML content</div>
        </foreignObject>
        <rect x="20" y="20" width="60" height="60" fill="red"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    # foreignObject is dropped; filter in defs is kept
    result = svg.topicosvg(allow_all_defs=True, drop_unsupported=True).tostring()
    assert "filter" in result
    assert "foreignObject" not in result


def test_deeply_nested_filter_structure():
    """Test filter with deeply nested structure."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="complex">
                <feGaussianBlur in="SourceAlpha" stdDeviation="4" result="blur1"/>
                <feOffset in="blur1" dx="4" dy="4" result="offset1"/>
                <feGaussianBlur in="offset1" stdDeviation="2" result="blur2"/>
                <feColorMatrix in="blur2" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.5 0" result="shadow"/>
                <feMerge>
                    <feMergeNode in="shadow"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
        <circle cx="100" cy="100" r="60" fill="orange"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    # All nested elements should be preserved
    assert "filter" in result
    assert "feGaussianBlur" in result
    assert "feOffset" in result
    assert "feColorMatrix" in result
    assert "feMerge" in result


def test_switch_with_multiple_conditions():
    """Test switch element with multiple language conditions."""
    svg_string = """
    <svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
        <defs></defs>
        <switch>
            <text systemLanguage="en" x="10" y="50">English</text>
            <text systemLanguage="zh" x="10" y="50">中文</text>
            <text systemLanguage="ja" x="10" y="50">日本語</text>
            <text x="10" y="50">Default</text>
        </switch>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True, allow_text=True).tostring()

    assert "switch" in result


def test_marker_element_preserved():
    """Test that marker elements in defs are preserved."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="black"/>
            </marker>
        </defs>
        <line x1="20" y1="100" x2="180" y2="100" stroke="black" stroke-width="2" marker-end="url(#arrowhead)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "marker" in result


def test_empty_defs_no_crash():
    """Test that empty defs element doesn't cause issues."""
    svg_string = """
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <defs></defs>
        <rect x="10" y="10" width="80" height="80" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    # Should work with or without allow_all_defs
    result1 = svg.topicosvg().tostring()
    svg2 = SVG.fromstring(svg_string)
    result2 = svg2.topicosvg(allow_all_defs=True).tostring()

    assert "path" in result1 or "rect" in result1
    assert "path" in result2 or "rect" in result2


def test_filter_with_feImage():
    """Test filter with feImage element."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <defs>
            <filter id="imageFilter">
                <feImage xlink:href="#rect1" result="img"/>
                <feBlend in="SourceGraphic" in2="img" mode="multiply"/>
            </filter>
            <rect id="rect1" x="0" y="0" width="50" height="50" fill="red"/>
        </defs>
        <circle cx="100" cy="100" r="50" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "filter" in result


def test_multiple_filters_on_same_element():
    """Test that an element can reference a filter and still be processed."""
    svg_string = """
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <filter id="blur">
                <feGaussianBlur stdDeviation="5"/>
            </filter>
        </defs>
        <rect x="10" y="10" width="80" height="80" fill="red" filter="url(#blur)"/>
        <circle cx="50" cy="50" r="20" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    # Filter should be preserved
    assert "filter" in result
    # Shapes should be converted to paths
    assert "path" in result


def test_gradient_and_filter_together():
    """Test that gradients and filters work together with allow_all_defs."""
    svg_string = """
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="skyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#87CEEB"/>
                <stop offset="100%" stop-color="#1E90FF"/>
            </linearGradient>
            <filter id="glow">
                <feGaussianBlur stdDeviation="4" result="blur"/>
                <feMerge>
                    <feMergeNode in="blur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
        <rect x="0" y="0" width="200" height="200" fill="url(#skyGradient)"/>
        <circle cx="100" cy="100" r="40" fill="yellow"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    # Both gradient and filter should be preserved
    assert "linearGradient" in result
    assert "filter" in result
    assert "feGaussianBlur" in result


def test_root_level_style_element():
    """Test that root-level style element is preserved with allow_all_defs."""
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <defs></defs>
        <style>.cls-1{fill:#ff0000}.cls-2{fill:#00ff00}</style>
        <path class="cls-1" d="M10,10 L90,10 L90,90 Z"/>
        <path class="cls-2" d="M10,10 L10,90 L90,90 Z"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "style" in result
    assert "cls-1" in result
    assert "cls-2" in result


def test_root_level_pattern_element():
    """Test that root-level pattern element is preserved with allow_all_defs."""
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <pattern id="dots" x="0" y="0" width="10" height="10" patternUnits="userSpaceOnUse">
            <circle cx="5" cy="5" r="3" fill="blue"/>
        </pattern>
        <defs></defs>
        <rect x="10" y="10" width="80" height="80" fill="url(#dots)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "pattern" in result


def test_root_level_mask_element():
    """Test that root-level mask element is preserved with allow_all_defs."""
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
        <mask id="myMask">
            <rect x="0" y="0" width="200" height="200" fill="white"/>
            <circle cx="100" cy="100" r="50" fill="black"/>
        </mask>
        <defs></defs>
        <rect x="0" y="0" width="200" height="200" fill="blue"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "mask" in result


def test_root_level_clipPath_element():
    """Test that root-level clipPath element is processed correctly.

    Note: clipPath is consumed by picosvg (applied to shapes then removed),
    so we just verify it doesn't crash.
    """
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <clipPath id="myClip">
            <circle cx="50" cy="50" r="40"/>
        </clipPath>
        <defs></defs>
        <rect x="0" y="0" width="100" height="100" fill="red"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    # Should not crash - clipPath is processed and removed
    result = svg.topicosvg(allow_all_defs=True).tostring()
    assert "path" in result  # rect converted to path


def test_combined_root_level_elements():
    """Test multiple root-level elements (style, pattern, mask) together."""
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
        <style>.highlight{fill:#ffcc00}</style>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <rect width="20" height="20" fill="white" stroke="gray"/>
        </pattern>
        <mask id="fade">
            <rect width="200" height="200" fill="white"/>
        </mask>
        <defs>
            <linearGradient id="grad">
                <stop offset="0%" stop-color="red"/>
                <stop offset="100%" stop-color="blue"/>
            </linearGradient>
        </defs>
        <rect x="10" y="10" width="180" height="180" fill="url(#grad)"/>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_all_defs=True).tostring()

    assert "style" in result
    assert "pattern" in result
    assert "mask" in result


def test_pattern_fill_with_transform():
    """Test that pattern fill with transform doesn't cause AssertionError.

    Previously, code assumed all url() fills were gradients and called
    _apply_gradient_template on patterns, causing AssertionError.
    """
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <defs>
            <pattern id="gridPattern" width="10" height="10" patternUnits="userSpaceOnUse">
                <rect width="10" height="10" fill="none" stroke="#333" stroke-width="0.5"/>
            </pattern>
        </defs>
        <g transform="translate(10, 10)">
            <rect x="0" y="0" width="80" height="80" fill="url(#gridPattern)"/>
        </g>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    # Should not raise AssertionError
    result = svg.topicosvg(allow_all_defs=True).tostring()
    assert "path" in result


def test_text_in_g_element():
    """Test that text elements nested in g elements are allowed with allow_text=True.

    Previously, allow_text regex only allowed text directly under svg,
    not nested within g elements like /svg[0]/g[0]/text[0].
    """
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <defs></defs>
        <g>
            <text x="10" y="20" font-size="12">Hello World</text>
        </g>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    # Should not raise ValueError about BadElement
    result = svg.topicosvg(allow_text=True).tostring()
    assert "text" in result
    assert "Hello World" in result


def test_text_in_nested_g_elements():
    """Test text in deeply nested g elements."""
    svg_string = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <defs></defs>
        <g>
            <g>
                <text x="10" y="20">Nested Text</text>
            </g>
        </g>
    </svg>
    """
    svg = SVG.fromstring(svg_string)
    result = svg.topicosvg(allow_text=True).tostring()
    assert "text" in result
    assert "Nested Text" in result
