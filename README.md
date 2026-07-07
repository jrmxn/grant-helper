# Grant Helper

A tool to split single grant PDFs (e.g. exported as a single google doc) and process SVG figures for submission.

## Prerequisites

- **Inkscape**: Required for SVG to PNG/PDF conversion. Ensure it is installed and available in your PATH.
- **Conda**: Required to provide the base Python environment.
- **Google Drive API Setup**: To enable automatic PDF downloads from Google Docs:
    1.  **Google Cloud Console**: Go to the [Google Cloud Console](https://console.cloud.google.com/).
    2.  **Create Project**: Create a new project (e.g., "Grant-Helper").
    3.  **Enable API**: In the "APIs & Services" dashboard, click "Enable APIs and Services", search for "Google Drive API", and enable it.
    4.  **Create Service Account**:
        *   Go to "APIs & Services" > "Credentials".
        *   Click "Create Credentials" > "Service Account".
        *   Give it a name and click "Create and Continue", then "Done".
    5.  **Generate JSON Key**:
        *   Click on the newly created Service Account.
        *   Go to the "Keys" tab.
        *   Click "Add Key" > "Create new key" > "JSON".
        *   The key file will download automatically. Save it in the project root directory.
    6.  **Share Google Doc**:
        *   Open your Google Doc.
        *   Open the JSON key file and find the `client_email` (e.g., `yourserviceaccount@project.iam.gserviceaccount.com`).
        *   Share your Google Doc with this email address with "Viewer" permissions.
    7.  **Extract Document ID**:
        *   Copy the Document ID from the URL of your Google Doc (the string between `/d/` and `/edit`).
        *   Add this ID to your `config.toml` or `env.json` as `gdrive_document_id`.

## Setup Instructions

Follow these steps to set up the local virtual environment:

1. **Activate the base Conda environment**:
   ```bash
   conda activate python-311
   ```

2. **Create the virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```cmd
     .\venv\Scripts\activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Configuration is managed via `config.toml`. You can also use a local `env.json` file to override paths without modifying the tracked TOML files.

### 1. Local Environment Overrides (`env.json`)
If `use_env_json = true` is set in the `[paths]` section of your TOML config, the script will look for an `env.json` file in the root directory. This is useful for machine-specific paths that should not be committed to version control.

Example `env.json` (Note: On Windows, use double backslashes `\\` or forward slashes `/` for paths):
```json
{
  "figure_directory": "/path/to/figures/",
  "pdf_path": "/path/to/downloaded.pdf",
  "output_dir": "/path/to/output/",
  "gdrive_document_id": "YOUR_DOCUMENT_ID",
  "gdrive_credentials_file": "credentials.json"
}
```

### 2. Configuration Sections:
- **`[paths]`**: 
    - `use_env_json`: Set to `true` to enable `env.json` overrides.
    - `gdrive_document_id`: (Optional) The ID of the Google Doc to export.
    - `gdrive_credentials_file`: (Optional) Path to your Google Cloud JSON key (defaults to `credentials.json`).
    - `pdf_path`, `figure_directory`, etc.: Standard path definitions.
- **`[sections]`**: Map grant section headings (as they appear in the PDF) to their desired output filenames.
- **`[processing]`**: Define `science_keys` (sections to exclude in 'science' mode) and `remove_hyperlinks` settings.
- **`[merge]`**: Define bundle sets. You can use section names (from the `[sections]` keys) OR direct absolute paths to existing PDF files.

### 3. Running the Script
Run the script by specifying a configuration file:
```bash
python main.py --config configs/2024_hbmep_r03.toml
```

You can use the following mutually exclusive flags to control which parts of the pipeline run:
- `--svg-only`: Skips downloading the Google Doc and splitting/merging the PDFs. Only processes SVG figures.
- `--skip-svg`: Skips processing of SVG figures, but downloads, splits, and merges PDFs as usual.

You can also use the following optional flags:
- `--remove-highlights`: Removes all text highlights (background colors) from the processed PDFs, leaving the underlying text intact. (By default, highlight deletion is skipped).
- `--flatten-pdf`: Routes every generated PDF through Ghostscript to effectively "Print to PDF". This completely sanitizes and rebuilds the PDF object structures, which resolves file corruption and slow-loading image errors when uploading attachments to NIH ASSIST.

Examples:
```bash
python main.py --config configs/2026_scap_r01_a0.toml --svg-only
python main.py --config configs/2026_scap_r01_a0.toml --skip-svg
```

### 4. Figure Management Workflow
To robustly manage figures and captions while keeping cross-references intact in Google Docs, follow this workflow:
1. **Design**: Create your figures in Inkscape (or similar) and save them as SVGs.
2. **Convert**: Run `grant-helper` to export these SVGs into high-quality PNGs.
3. **Stage in Google Docs**: At the end of your Google Doc, create a dedicated `FIGURES` section. For each figure, insert a 2-cell table (one table per page). Place the generated PNG in the top cell and write the figure caption in the bottom cell. 
4. **Extract**: When you run `grant-helper`, it automatically scans the `FIGURES` section and takes a tight, high-resolution (300 DPI) screenshot of each table. 
5. **Re-insert**: These extracted screenshots (combining the figure and caption into one image) are saved sequentially (e.g. `fig01.png`, `fig02.png`). You can now insert these fully compiled images back into the appropriate locations within your main narrative.

By grouping the image and caption into a single image via the `FIGURES` section, you can safely use Google Docs' cross-referencing features in your narrative without reordering issues breaking your captions or references.

### 5. Output Directory Structure
When the script runs, it generates several subdirectories inside your configured `output_dir`:
- **`wip/main/`**: Contains all standard sections extracted from the PDF and the final merged bundles.
- **`wip/ignore/`**: Contains sections that are excluded from the main processing (e.g., internal notes).
- **`wip/figures/`**: If your grant has a `FIGURES` section, the script will automatically take a high-resolution (300 DPI) screenshot of the table/content on each page of that section (skipping the first page). These screenshots are saved here sequentially as `fig01.png`, `fig02.png`, etc.
- **`archive/`**: At the end of a run, the `main`, `ignore`, and `figures` folders are compressed into a `tar.gz` archive and saved here (alongside the `wip` folder) with a datetime stamp.

### 6. Automatic Modifications
During processing, the script automatically performs several cleanup operations on the generated PDFs:
- **AUTOREMOVE Footers**: The script searches every page for text matching the pattern `[AUTOREMOVE: X]` (where X is any number). It cleanly removes this text and its underlying vector paths without leaving any redaction boxes.
- **Hyperlinks**: By default, all clickable hyperlinks are removed from the document (except in `BIOSKETCH` sections) to comply with submission guidelines.
- **Highlights**: Controlled via the `--remove-highlights` flag. If enabled, it deletes all PDF highlight annotations.

### Strict Mode
By default, the script operates in **strict mode**. If any section defined in your TOML is not found in the PDF, or if any file path in a merge set is missing, the script will raise an error and exit.

To disable this behavior (e.g., for debugging), use the `--lax` flag:
```bash
python main.py --config configs/2026_dapr.toml --lax
```
