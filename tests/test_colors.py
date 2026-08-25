from colors import map_palette, parse_scheme_lines


def test_parse_scheme_ignores_hooks():
    text = "kitty_reload: ok!\n#12333D\n#4E5F5C\n#626C69\n#807467\n#6A8164\n#858E82\n#899575\n#E8EBDD\n"
    colors = parse_scheme_lines(text)
    assert colors[0] == "#12333D"
    assert colors[-1] == "#E8EBDD"
    assert len(colors) == 8


def test_map_palette_has_required_keys():
    scheme = [
        "#12333D",
        "#4E5F5C",
        "#626C69",
        "#807467",
        "#6A8164",
        "#858E82",
        "#899575",
        "#E8EBDD",
        "#2A4A54",
        "#5E7C77",
        "#81938E",
        "#A68C71",
        "#6FA461",
        "#ADC2A6",
        "#B5D289",
        "#E8EBDD",
    ]
    mapped = map_palette(scheme, style="dark")
    for key in ("background", "ui_accent", "ui_text", "ui_ok", "ui_error", "ui_warn", "ui_border"):
        assert mapped[key].startswith("#")
        assert len(mapped[key]) == 7
    # Dark wallpaper → dark background, light text
    assert mapped["background"].upper() == "#12333D"
    assert mapped["ui_text"].upper() == "#E8EBDD"
