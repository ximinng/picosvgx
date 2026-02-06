# picosvgx

An extended fork of Google's picosvg with better real-world SVG compatibility.

## Why picosvgx?

picosvg is excellent for font/icon toolchains — it simplifies SVG files down to paths and gradients. But real-world SVG files are messy:

- They use CSS units (`12pt`, `100px`, `2cm`)
- They miss namespace declarations
- They contain `<filter>`, `<mask>`, `<pattern>` that you might want to preserve
- They have edge cases that cause crashes

picosvgx handles these gracefully.

## What's Different

| | picosvg | picosvgx |
|---|---------|----------|
| CSS units (`pt`, `cm`, `mm`) | Crashes | Parsed correctly |
| Missing SVG namespace | Crashes | Auto-fixed |
| `<filter>`, `<mask>`, `<pattern>` | Removed | Preserved (opt-in) |
| Empty `<clipPath>` | Crashes | Handled |
| Degenerate transforms | Crashes | Handled |
| Nested `<text>` in `<g>` | Not allowed | Supported |

## Installation

```bash
pip install picosvgx
```

## Usage

### Python API

```python
from picosvgx.svg import SVG

# Basic usage (same as picosvg)
svg = SVG.parse("input.svg")
result = svg.topicosvg()
print(result.tostring())

# Preserve filters, masks, patterns
result = svg.topicosvg(allow_all_defs=True)
```

### CLI

```bash
# Simplify SVG
picosvgx input.svg > output.svg

# Preserve filters, masks, patterns
picosvgx --allow_all_defs input.svg > output.svg

# Allow text pass-through
picosvgx --allow_text input.svg > output.svg
```

## Development

```bash
pip install -e '.[dev]'
pytest
```

## Compatibility

picosvgx maintains full API compatibility with picosvg. Drop-in replacement:

```python
# Before
from picosvg.svg import SVG

# After
from picosvgx.svg import SVG
```

## Credits

Based on [picosvg](https://github.com/googlefonts/picosvg) by Google Fonts. Original work Copyright 2020 Google LLC.

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
