"""Tool schemas — what the LLM sees."""

APPLY = {
    "name": "wallust_theme_apply",
    "description": (
        "Generate a Hermes UI skin from an image using wallust (the same "
        "k-means / salience / ANSI palette algorithm as "
        "https://codeberg.org/explosion-mental/wallust) and apply it live "
        "to CLI, TUI, and the desktop app. Defaults to the current GNOME "
        "wallpaper. Use when the user asks to match Hermes colors to the "
        "wallpaper, regenerate the wallust theme, or restyle Hermes from "
        "a picture."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image": {
                "type": "string",
                "description": "Path to an image. Omit to use the current GNOME wallpaper.",
            },
            "style": {
                "type": "string",
                "enum": ["auto", "dark", "light"],
                "description": "Palette polarity. auto follows GNOME color-scheme.",
            },
            "activate": {
                "type": "boolean",
                "description": "Write AND activate the skin (default true). false only writes the YAML.",
            },
        },
    },
}

STATUS = {
    "name": "wallust_theme_status",
    "description": (
        "Show the last wallust-generated Hermes skin: wallpaper path, "
        "style, palette, and whether the wallpaper watcher is running."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}
