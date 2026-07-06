SuperSearch
===========

Technical documentation and operation guide.

SuperSearch is a desktop application for searching, analyzing, and extracting content from internal document repositories. It is designed for procedure documents, policies, forms, manuals, contracts, and other business files.


Overview
--------

SuperSearch helps users search internal knowledge quickly, visually, and fully offline. The application converts documents to Markdown, builds a local search index, and enables full-text search directly on the user's computer.

Key highlights:
- Local processing.
- No server required.
- No document content is sent outside the computer.
- Integrated OCR for scanned PDFs and images.
- Offline indexing.
- Fast full-text search.
- Quick document preview inside the application.
- Filtering by file type, year, and keywords.


Core Value
----------

1. Fast response

The integrated interface and local search index return results almost instantly. Users can search as they type and refine results without network latency.

2. Data privacy

File scanning, Markdown conversion, and optical character recognition run locally. The application does not need a remote server to process document content.

3. Quick preview

Users can preview converted Markdown or PDF content inside the application. Search keywords are highlighted for fast comparison.

4. Multi-dimensional filtering

The application can classify documents by department, business domain, and document type. Examples include IT, HSSE, Finance, HR, Operation, Marketing, Procedure, Policy, and Contract.


Technical Architecture
----------------------

SuperSearch runs as an offline desktop application. Python handles document conversion, OCR, and index generation. The WebView frontend displays the search interface and performs search over a static JavaScript index.

Main components:
- Python backend for file processing, OCR, and indexing.
- WebView frontend for the search interface.
- Markdown as the normalized intermediate format.
- Static JavaScript search index for offline lookup.
- Bundled local Tesseract-OCR engine.


Document Conversion Pipeline
----------------------------

SuperSearch integrates custom converters based on Microsoft MarkItDown.

LocalOcrPdfConverter:
- Extracts text from PDF files with pdfplumber.
- Automatically calls Tesseract-OCR when a PDF appears to be scanned.
- Supports Vietnamese and English recognition.

LocalOcrImageConverter:
- Performs OCR on PNG, JPG, and JPEG images.
- Useful for document screenshots and chat images.

LocalDocConverter:
- Reads legacy Word .doc files.
- Decodes UTF-16LE content.
- Recovers broken ANSI characters where possible.
- Filters unwanted CJK noise characters.

LocalXlsConverter:
- Reads legacy Excel .xls files.
- Converts table content into Markdown.


Resource Management
-------------------

SuperSearch uses RAM-aware multi-threading to reduce the risk of freezing the computer during large indexing jobs.

Main behavior:
- Monitors system RAM through the Windows Kernel API.
- Reduces processing to a single worker when RAM usage is high.
- Uses available CPU capacity when the computer is idle.
- Supports pause, resume, and abort controls during indexing.


Offline Search Database
-----------------------

SuperSearch does not depend on Elasticsearch, SQLite, or a database server. The search index is stored as a static JavaScript file.

Characteristics:
- Each scanned folder gets a separate index file.
- The index file name uses an MD5 hash of the folder path.
- The WebView loads the index directly through a script tag.
- Full-text search runs offline without network access.


Automatic Document Classification
---------------------------------

SuperSearch assigns metadata based on content, file name, and folder structure.

Classification criteria:
- Empty forms and draft-like files.
- OCR quality.
- Business domain.
- Document type.
- Language.
- Year of issue or creation.

Metadata examples:
- Empty Form Template.
- Real Content.
- Error Reading.
- IT, HSSE, HR, Operation, Finance, Marketing.
- Policy.
- Procedure or Guideline.
- Decision or Minutes.
- Vietnamese, English, or bilingual.


Operation Guide
---------------

Indexing a new document folder:

1. Start the application

Double-click SuperSearch.exe to launch the app.

2. Select a document folder

Click the folder icon in the interface and select the folder that contains the documents to index.

3. Run indexing

The system converts supported files and creates the search index. Indexing progress is shown in real time.

4. Search

Type keywords into the search bar. Results are ranked by relevance.

5. Preview content

Click a result or the quick-view icon to open converted content inside the application.


Keyboard Shortcuts
------------------

Enter:
- Run a search query.

Up / Down arrow:
- Move between result rows.

Space:
- Open or close Quick Preview.

Double-click on a result:
- Open the original file with the default Windows application.

Right click -> Find in Explorer:
- Open Windows Explorer and locate the selected file.

Esc:
- Close the preview window or active dialog.


Notes About Drafts and Low-Quality Files
----------------------------------------

The system may filter or label files as drafts when they look like empty forms, contain too little real content, or include heavy OCR noise.

To help documents be recognized as real content:
- Avoid naming real documents with the word "draft".
- Make sure files contain meaningful content.
- Avoid very blurry scans or files with missing pages.


Privacy and Security
--------------------

SuperSearch is designed for internal document environments. Document content is processed on the user's computer.

By default:
- Document content is not sent outside the computer.
- No database server is required.
- No external API is required for search.
- The index is created and read locally.


License
-------

Copyright (c) 2026 SuperSearch by DVC.

Apache 2.0 license.

