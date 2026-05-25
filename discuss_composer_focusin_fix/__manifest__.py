{
    "name": "Discuss Composer Focusin Fix",
    "version": "19.0.1.0.0",
    "summary": "Fix TypeError: Cannot read properties of undefined (reading 'stopPropagation') in Composer.onFocusin",
    "description": """
Patches the Discuss Composer component to guard against an undefined event
argument in onFocusin, which raises:

    TypeError: Cannot read properties of undefined (reading 'stopPropagation')

This can occur when the focusin handler is invoked programmatically
(without a real DOM Event) during owl rendering / focus restoration.
""",
    "category": "Productivity/Discuss",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": ["mail"],
    "assets": {
        "web.assets_backend": [
            "discuss_composer_focusin_fix/static/src/composer_patch.js",
        ],
        "mail.assets_public": [
            "discuss_composer_focusin_fix/static/src/composer_patch.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
