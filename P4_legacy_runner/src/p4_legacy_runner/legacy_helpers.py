from __future__ import print_function

import argparse
import logging
import os
import sys


def add_import_paths(p4_app_path):
    paths = [
        p4_app_path,
        os.path.join(p4_app_path, "GenerateLists"),
        os.path.join(p4_app_path, "CheckIndex"),
        os.path.join(p4_app_path, "XSL-FO"),
    ]
    for path in reversed(paths):
        if path not in sys.path:
            sys.path.insert(0, path)


def setup_logging(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s:%(name)s:%(message)s")


def setup_legacy_services(p4_app_path):
    add_import_paths(p4_app_path)
    import P4Locale

    P4Locale.force_utf8_hack()

    import Configurator
    import FamilyProject
    import ImagesManager
    import StylesheetManager
    import TexmlProject

    publisher_ini = os.path.join(p4_app_path, "publisher.ini")
    config = Configurator.AppConfig(publisher_ini)
    stylesheet_manager = StylesheetManager.StylesheetSet(config)
    images_manager = ImagesManager.ImageDirSet(config)
    p2_project_manager = TexmlProject.ProjectManager(
        config,
        stylesheet_manager,
        images_manager,
    )
    project_manager = FamilyProject.FamilyProjectManager(config, p2_project_manager)
    return config, project_manager


def find_project(project_manager, project_path, project_name=None):
    if not project_path:
        return None
    project_path = os.path.abspath(project_path)
    projects = project_manager.find_projects_in_dir(project_path)
    if len(projects) != 1:
        name = project_name
        if name is None:
            name = os.path.basename(project_path)
        elif ":" not in name:
            name = os.path.basename(project_path) + ":" + name
        projects = [project for project in projects if project.get_name() == name]
    if len(projects) != 1:
        raise RuntimeError(
            "Expected one project in {0}, got {1}".format(project_path, len(projects))
        )
    return projects[0]


def run_generate_lists(args):
    config, project_manager = setup_legacy_services(args.p4_app_path)
    project = find_project(project_manager, args.project_path, args.project_name)
    from list_generator import process_generate_lists

    result = process_generate_lists(
        config,
        project,
        output_dir=args.output_dir,
        xml_file_path=args.xml_file,
    )
    if not result:
        print("Generate lists did not produce an output file.", file=sys.stderr)
        return 2
    print("RESULT {0}".format(result))
    return 0


def run_check_index(args):
    config, project_manager = setup_legacy_services(args.p4_app_path)
    project = find_project(project_manager, args.project_path, args.project_name)
    from index_repair import process_check_index

    result = process_check_index(
        project,
        xml_file_path=args.xml_file,
        basedir=args.p4_app_path,
    )
    if result is None:
        print("Check index did not apply or could not run.", file=sys.stderr)
        return 2
    path, replacements = result
    print("RESULT {0} replacements={1}".format(path, replacements))
    return 0


def run_xsl_fo(args):
    config, project_manager = setup_legacy_services(args.p4_app_path)
    project = find_project(project_manager, args.project_path, args.project_name)
    from xsl_fo import process_xslfo_document

    pdf_file, validation_errors, validation_skipped = process_xslfo_document(
        config,
        project,
        output_dir=args.output_dir,
        xml_file_path=args.xml_file,
    )
    if validation_errors:
        for message in validation_errors:
            print("VALIDATION {0}".format(message))
    if validation_skipped:
        print("VALIDATION_SKIPPED true")
    if not pdf_file:
        print("XSL-FO did not produce a PDF file.", file=sys.stderr)
        return 2
    print("RESULT {0}".format(pdf_file))
    return 0


def run_convert_sap_to_bit_xml(args):
    setup_legacy_services(args.p4_app_path)
    import Configurator
    import Language
    import Transformation

    publisher_ini = os.path.join(args.p4_app_path, "publisher.ini")
    config = Configurator.AppConfig(publisher_ini)
    etk_file = os.path.abspath(args.etk_file)
    output_file = args.output_file or Language.inject_infix(etk_file, "bitplant")
    template_file = config.get_resource_file("generate_xml", "etk_table_template.xml")

    env = Transformation.TransformationEnvironment()
    node = env.XmlFile(template_file)
    node = env.CastToXmldocNode(node)
    node = env.GenerateEtkTable(node, [etk_file])
    node = env.XmldocToFile(node, output_file)
    env.build([node])
    if not os.path.isfile(output_file):
        print("SAP to bitplant XML did not produce an output file.", file=sys.stderr)
        return 2
    print("RESULT {0}".format(output_file))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="legacy_helpers.py")
    parser.add_argument(
        "command",
        choices=["generate-lists", "check-index", "xsl-fo", "convert-sap-to-bit-xml"],
    )
    parser.add_argument("--p4-app-path", required=True)
    parser.add_argument("--project-path")
    parser.add_argument("--project-name")
    parser.add_argument("--xml-file")
    parser.add_argument("--output-dir")
    parser.add_argument("--output-file")
    parser.add_argument("--etk-file")
    parser.add_argument("--language", default="de")
    parser.add_argument("--debug", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.debug)
    args.p4_app_path = os.path.abspath(args.p4_app_path)
    os.chdir(args.p4_app_path)

    if args.command == "generate-lists":
        return run_generate_lists(args)
    if args.command == "check-index":
        return run_check_index(args)
    if args.command == "xsl-fo":
        return run_xsl_fo(args)
    if args.command == "convert-sap-to-bit-xml":
        if not args.etk_file:
            parser.error("--etk-file is required for convert-sap-to-bit-xml")
        return run_convert_sap_to_bit_xml(args)
    parser.error("Unsupported helper command: {0}".format(args.command))
    return 2


if __name__ == "__main__":
    sys.exit(main())
