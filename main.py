import fitz  # PyMuPDF
import io
import json
import os
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False


def export_doc_to_pdf(document_id, output_filepath, credentials_file='credentials.json'):
    if not HAS_GDRIVE:
        raise ImportError("google-api-python-client and google-auth are required for Google Drive export.")

    # Authenticate and build service
    scopes = ['https://www.googleapis.com/auth/drive.readonly']
    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=scopes)
    service = build('drive', 'v3', credentials=creds)

    try:
        # Execute export request
        request = service.files().export_media(
            fileId=document_id,
            mimeType='application/pdf'
        )

        # Write stream to local file
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

        with open(output_filepath, 'wb') as f:
            f.write(file.getvalue())
        print(f"Exported Google Doc {document_id} to {output_filepath}")
    except HttpError as error:
        if error.resp.status == 404:
            print(f"\nError: Google Drive Document with ID '{document_id}' not found.")
            print("\nDebugging Steps:")
            print(f"1. The document hasn't been shared with the service account. Share the Google Doc with:\n   {creds.service_account_email}\n   as a Viewer or Editor.")
            print("2. The Document ID is incorrect. Double-check that the ID in your config exactly matches the ID in the URL of your Google Doc.")
            exit(1)
        else:
            raise


def find_and_split_pdf(pdf_path, main_output_dir, ignore_output_dir, sections_config, processing_config, output_type='all',
                        attach_string='datetime', strict=True):
    # Ensure output directories exist
    os.makedirs(main_output_dir, exist_ok=True)
    os.makedirs(ignore_output_dir, exist_ok=True)

    saved_paths = {}

    if attach_string == 'datetime':
        now = datetime.now()
        strformat = '%Y-%m-%dT%H'
        formatted_date = now.strftime(strformat)
        es = f'_{formatted_date}'
    else:
        es = ''

    # Open the PDF
    doc = fitz.open(pdf_path)

    # Define all sections and their output filenames
    sections_full = sections_config

    if output_type == 'all':
        sections = sections_full.copy()
    elif output_type == 'science':
        sections = sections_full.copy()
        keys = processing_config.get("science_keys", [])
        for key in keys:
            sections.pop(key, None)
    else:
        sections = {output_type: sections_full.get(output_type)}

    section_starts = {key: None for key in sections.keys()}

    # Search each page for the headings
    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        for section in sections.keys():
            # this is not perfect, e.g. if a word of a later part is in the earlier one
            if section in text:
                section_starts[section] = page_num
                break  # Move to the next page once a section is found

    # Strict check: Ensure all sections were found
    missing_sections = [s for s, start in section_starts.items() if start is None]
    if missing_sections:
        error_msg = f"The following sections were not found in the PDF: {', '.join(missing_sections)}"
        if strict:
            raise ValueError(f"Error: {error_msg}")
        else:
            print(f"Warning: {error_msg} (Skipping due to lax mode)")

    sorted_sections = sorted(section_starts.items(), key=lambda x: x[1] if x[1] is not None else float('inf'))

    # Create a mapping for auto-numbering based on TOML order
    toml_order = {section_name: i for i, section_name in enumerate(sections_config.keys())}

    for i, (section, start_page) in enumerate(sorted_sections):
        if start_page is None:
            continue

        end_page = sorted_sections[i + 1][1] if i + 1 < len(sorted_sections) else len(doc)
        
        if end_page is None:
             # If the next section wasn't found, we take all pages until the end of the doc
             found_next = False
             for j in range(i + 1, len(sorted_sections)):
                 if sorted_sections[j][1] is not None:
                     end_page = sorted_sections[j][1]
                     found_next = True
                     break
             if not found_next:
                 end_page = len(doc)

        section_doc = fitz.open()  # Create a blank document
        for pn in range(start_page, end_page):
            section_doc.insert_pdf(doc, from_page=pn, to_page=pn)

        # Determine the output filename and directory
        output_filename = sections[section]
        name, extension = output_filename.rsplit('.', 1)
        
        # Prepend auto-numbering index from TOML order
        index = toml_order.get(section, 99)
        output_filename = f"{index:02d}_{name}{es}.{extension}"

        if "_IGNORE" in output_filename:
            output_path = os.path.join(ignore_output_dir, output_filename)
        else:
            output_path = os.path.join(main_output_dir, output_filename)

        # Remove hyperlinks if requested, except for BIOSKETCHES
        if processing_config.get("remove_hyperlinks", True) and "BIOSKETCH" not in section.upper():
            links_count = 0
            for page in section_doc:
                links = page.get_links()
                for link in links:
                    page.delete_link(link)
                    links_count += 1
            if links_count > 0:
                print(f"Removed {links_count} hyperlinks from section '{section}'.")

        # Save the section
        section_doc.save(output_path)
        section_doc.close()
        saved_paths[section] = output_path
        print(f"Saved section '{section}' to '{output_path}'.")

    # Close the original document
    doc.close()
    os.unlink(pdf_path)
    return saved_paths


def merge_sets(saved_paths, merge_config, processing_config, output_dir, strict=True):
    if not merge_config or "sets" not in merge_config:
        return

    os.makedirs(output_dir, exist_ok=True)
    current_datetime = datetime.now().strftime("%Y-%m-%dT%H")
    remove_links = processing_config.get("remove_hyperlinks", True)

    for merge_set in merge_config["sets"]:
        set_name = merge_set["name"]
        sections_to_merge = merge_set["sections"]
        preamble = merge_config.get("preamble", "")
        prefix = f"{preamble}_" if preamble else ""

        merged_pdf = fitz.open()
        files_merged = []

        for section in sections_to_merge:
            # Check if it's a section key from the split process
            if section in saved_paths:
                file_path = saved_paths[section]
                pdf_doc = fitz.open(file_path)
                # Hyperlinks are already removed in find_and_split_pdf
                merged_pdf.insert_pdf(pdf_doc)
                pdf_doc.close()
                files_merged.append(section)
            # Check if it's a direct path to an existing file
            elif os.path.exists(section) and section.lower().endswith(".pdf"):
                pdf_doc = fitz.open(section)
                
                # Apply hyperlink removal for external files if requested (skip BIOSKETCHES)
                if remove_links and "BIOSKETCH" not in section.upper():
                    links_count = 0
                    for page in pdf_doc:
                        links = page.get_links()
                        for link in links:
                            page.delete_link(link)
                            links_count += 1
                    if links_count > 0:
                        print(f"Removed {links_count} hyperlinks from external file '{os.path.basename(section)}'.")
                
                merged_pdf.insert_pdf(pdf_doc)
                pdf_doc.close()
                files_merged.append(f"External({os.path.basename(section)})")
            else:
                error_msg = f"Section or Path '{section}' not found, skipping in merge set '{set_name}'."
                if strict:
                    raise ValueError(f"Error: {error_msg}")
                else:
                    print(f"Warning: {error_msg}")

        if files_merged:
            output_filename = f"{prefix}merged_{set_name}_{current_datetime}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            merged_pdf.save(output_path)
            merged_pdf.close()
            print(f"Created merged PDF '{output_path}' from sections: {', '.join(files_merged)}")
        else:
            merged_pdf.close()
            print(f"Skipping merge set '{set_name}' as no sections were found.")


def process_svg_files(target_dir):
    # Ensure target directories for png and pdf exist
    png_dir = os.path.join(target_dir, 'png')
    pdf_dir = os.path.join(target_dir, 'pdf')
    os.makedirs(png_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)

    # Define the command template for Inkscape conversion
    cmd_template_png = 'inkscape --export-type="png" --export-area-page --export-dpi=600 "{path}" && mv "{path_no_ext}.png" "{output_dir}"'
    cmd_template_pdf = 'inkscape --export-type="pdf" --export-area-page "{path}" && mv "{path_no_ext}.pdf" "{output_dir}"'

    # Walk through the directory to find .svg files, excluding the 'wip_ignore' folder
    for root, dirs, files in os.walk(target_dir):
        if 'wip_ignore' in dirs:
            dirs.remove('wip_ignore')  # Do not traverse into the 'wip_ignore' directory

        for file in files:
            if file.endswith('.svg'):
                file_path = os.path.join(root, file)
                file_path_no_ext = os.path.splitext(file_path)[0]

                # Execute PNG conversion
                cmd_png = cmd_template_png.format(path=file_path, path_no_ext=file_path_no_ext, output_dir=png_dir)
                subprocess.run(cmd_png, shell=True, check=True)

                # Execute PDF conversion
                cmd_pdf = cmd_template_pdf.format(path=file_path, path_no_ext=file_path_no_ext, output_dir=pdf_dir)
                subprocess.run(cmd_pdf, shell=True, check=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Split NIH grant PDFs and process SVG figures.")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration TOML file"
    )
    parser.add_argument(
        "--lax",
        action="store_true",
        help="Allow missing sections or files instead of raising an error"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--svg-only",
        action="store_true",
        help="Only process SVG figures and skip PDF processing"
    )
    group.add_argument(
        "--skip-svg",
        action="store_true",
        help="Skip processing of SVG figures"
    )
    args = parser.parse_args()
    strict_mode = not args.lax

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file '{config_path}' not found.")
        exit(1)

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    paths = config["paths"]
    
    if paths.get("use_env_json", False):
        env_path = Path("env.json")
        if env_path.exists():
            with open(env_path, "r") as env_f:
                env_config = json.load(env_f)
                paths.update(env_config)
                print(f"Loaded path overrides from {env_path}")
        else:
            print(f"Warning: 'use_env_json' is True but '{env_path}' not found.")

    sections = config["sections"]
    processing = config["processing"]
    los = config.get("los", {})
    merge = config.get("merge", {})

    if paths.get("gdrive_document_id") and not args.svg_only:
        export_doc_to_pdf(
            paths["gdrive_document_id"],
            paths["pdf_path"],
            paths.get("gdrive_credentials_file", "credentials.json")
        )

    if not args.skip_svg:
        process_svg_files(paths["figure_directory"])

    if args.svg_only:
        print("SVG processing complete. Exiting due to --svg-only flag.")
        exit(0)

    saved_paths = find_and_split_pdf(
        paths["pdf_path"],
        paths["main_output_dir"],
        paths["ignore_output_dir"],
        sections,
        processing,
        output_type='all',
        attach_string=processing.get("attach_string", "datetime"),
        strict=strict_mode
    )

    # Generic merge sets
    merge_sets(saved_paths, merge, processing, paths["main_output_dir"], strict=strict_mode)
