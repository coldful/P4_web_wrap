"""Legacy operation registry.

This module is intentionally Python 2.7 compatible. The runner may execute inside
the same old runtime that hosts P4_app.
"""

INTERFACE_OPERATIONS = {
    "generate-pdf": {
        "web_kind": "generate_pdf",
        "flag": "--topdf",
        "requires_project": True,
        "artifact_globs": ["*.pdf", "**/*.pdf"],
        "mutates_project": False,
        "description": "Generate PDF through P4_app/interface.py.",
    },
    "generate-html": {
        "web_kind": "generate_html",
        "flag": "--tohtml",
        "requires_project": True,
        "artifact_globs": ["*.html", "**/*.html", "**/*.css", "**/*.js", "**/media/**"],
        "mutates_project": False,
        "description": "Generate HTML through P4_app/interface.py.",
    },
    "cut-source": {
        "web_kind": "cut_source",
        "flag": "--cut-source",
        "requires_project": True,
        "artifact_globs": ["**/*.xml"],
        "mutates_project": True,
        "description": "Run the legacy cut-source chain.",
    },
    "export-translation": {
        "web_kind": "export_translation",
        "flag": "--export-translation",
        "requires_project": True,
        "artifact_globs": ["**/*translation*", "**/*.xml", "**/*.zip"],
        "mutates_project": False,
        "requires_language": True,
        "description": "Export translation package/files for one language.",
    },
    "import-translation": {
        "web_kind": "import_translation",
        "flag": "--import-translation",
        "requires_project": True,
        "artifact_globs": ["**/*.xml"],
        "mutates_project": True,
        "requires_language": True,
        "description": "Import translated files into the project workspace.",
    },
    "pack-modules": {
        "web_kind": "pack_modules",
        "flag": "--pack",
        "requires_project": True,
        "artifact_globs": ["**/*.xml", "**/packed.txt"],
        "mutates_project": True,
        "description": "Pack text modules through the legacy module packer.",
    },
    "unpack-modules": {
        "web_kind": "unpack_modules",
        "flag": "--unpack",
        "requires_project": True,
        "artifact_globs": ["**/*.xml", "**/unpacked.txt"],
        "mutates_project": True,
        "description": "Unpack text modules through the legacy module packer.",
    },
    "trunk-to-branch": {
        "web_kind": "trunk_to_branch",
        "flag": "--trunk2branch",
        "requires_project": True,
        "artifact_globs": ["**/*.xml"],
        "mutates_project": True,
        "description": "Convert trunk XML to branch XML.",
    },
    "downgrade-to-p2": {
        "web_kind": "downgrade_to_p2",
        "flag": "--p2",
        "requires_project": True,
        "artifact_globs": ["**/*_TeX_*"],
        "mutates_project": True,
        "description": "Downgrade P4 project output to P2/TeX project files.",
    },
    "aladin": {
        "web_kind": "aladin",
        "flag": "--aladin",
        "requires_project": True,
        "artifact_globs": ["**/*.html", "**/*.pdf"],
        "mutates_project": False,
        "description": "Run Aladin mass HTML/PDF generation for selected codes.",
    },
    "opmanual-to-bit-xml": {
        "web_kind": "convert_opmanual_to_bit_xml",
        "flag": "--opmanual-to-bitplant",
        "requires_project": False,
        "artifact_globs": ["**/*.xml"],
        "mutates_project": True,
        "description": "Convert opmanual XML files to bitplant XML.",
    },
    "convert-image": {
        "web_kind": "convert_image",
        "flag": "--convert-image",
        "requires_project": False,
        "artifact_globs": ["**/*.png", "**/*.pdf", "**/*.eps"],
        "mutates_project": False,
        "description": "Upload/convert one image through legacy image handling.",
    },
    "convert-images": {
        "web_kind": "convert_images",
        "flag": "--convert-images",
        "requires_project": False,
        "artifact_globs": ["**/*.png", "**/*.pdf", "**/*.eps"],
        "mutates_project": False,
        "description": "Upload/convert one configured image set.",
    },
    "create-project": {
        "web_kind": "legacy_create_project",
        "flag": "--create",
        "requires_project": False,
        "artifact_globs": ["**/*.proj.xls", "**/*.proj.xlsm"],
        "mutates_project": True,
        "description": "Create a legacy project using client and project name.",
    },
    "set-var": {
        "web_kind": "legacy_set_var",
        "flag": "--setvar",
        "requires_project": True,
        "artifact_globs": ["**/*.proj.xls", "**/*.proj.xlsm"],
        "mutates_project": True,
        "description": "Set one project key/value variable.",
    },
    "server-config": {
        "web_kind": "legacy_server_config",
        "flag": "--server-config",
        "requires_project": False,
        "artifact_globs": [],
        "mutates_project": False,
        "description": "Update legacy server connection settings.",
    },
}

HELPER_OPERATIONS = {
    "texml-pdf": {
        "web_kind": "texml_pdf",
        "requires_project": True,
        "artifact_globs": [
            "_texml_pdf/**/*.pdf",
            "_texml_pdf/**/*.tex",
            "_texml_pdf/**/*.texml",
            "_texml_pdf/**/*.log",
        ],
        "mutates_project": False,
        "description": "Run legacy TeXML/P2 SCons PDF generation.",
    },
    "generate-lists": {
        "web_kind": "generate_lists",
        "requires_project": True,
        "artifact_globs": ["**/*_with_lists.xml"],
        "mutates_project": True,
        "description": "Generate figure/table lists through GenerateLists/list_generator.py.",
    },
    "check-index": {
        "web_kind": "check_index",
        "requires_project": True,
        "artifact_globs": ["**/*.xml"],
        "mutates_project": True,
        "description": "Apply index.xml repair rules through CheckIndex/index_repair.py.",
    },
    "xsl-fo": {
        "web_kind": "xsl_fo",
        "requires_project": True,
        "artifact_globs": ["**/*.fo", "**/*.pdf"],
        "mutates_project": False,
        "description": "Run XSL-FO processing through XSL-FO/xsl_fo.py.",
    },
    "convert-sap-to-bit-xml": {
        "web_kind": "convert_sap_to_bit_xml",
        "requires_project": False,
        "artifact_globs": ["**/*.xml"],
        "mutates_project": False,
        "description": "Convert ETK/SAP XML export to bitplant XML.",
    },
    "advance-delivery-status": {
        "web_kind": "advance_delivery_status",
        "requires_project": True,
        "artifact_globs": [
            "**/*.proj.xls",
            "**/*.proj.xlsm",
            "001/**",
            "002/**",
            "003/**",
            "004/**",
            "005/**",
            "pdf/**",
        ],
        "mutates_project": True,
        "description": "Advance delivery_status through FamilyProject.advance_delivery_status().",
    },
}


def all_operations():
    names = sorted(list(INTERFACE_OPERATIONS.keys()) + list(HELPER_OPERATIONS.keys()))
    return names


def operation_spec(name):
    if name in INTERFACE_OPERATIONS:
        spec = INTERFACE_OPERATIONS[name].copy()
        spec["runner"] = "interface"
        return spec
    if name in HELPER_OPERATIONS:
        spec = HELPER_OPERATIONS[name].copy()
        spec["runner"] = "helper"
        return spec
    raise KeyError(name)
