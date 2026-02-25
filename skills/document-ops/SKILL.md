---
name: "document-ops"
description: "Handles CRUD operations for TXT, Word, and PDF files. Invoke when user needs to read, write, edit, or delete document files."
---

# Document Operations

This skill enables the agent to perform Create, Read, Update, and Delete (CRUD) operations on various document formats including TXT, Word (DOCX), and PDF.

## Capabilities

- **TXT**: Read content, write new content, append text, delete files.
- **Word (DOCX)**: Read text, create new documents, add paragraphs/tables, modify existing content (requires `python-docx`).
- **PDF**: Extract text, merge PDFs, split PDFs, create simple PDFs (requires `PyPDF2` or `reportlab`).

## Implementation Strategy

Since the agent environment may not have native tools for direct binary file manipulation, this skill relies on Python scripts.

1.  **Check Dependencies**:
    - For Word: `python-docx`
    - For PDF: `PyPDF2`, `pdfminer.six`, or `reportlab`
    - Install missing dependencies using `pip install`.

2.  **Operation Logic**:
    - **Read**: Write a Python script to open the file and print its content to stdout, then capture the output.
    - **Write/Edit**: Write a Python script to open the file (or create a new one) and modify it using the appropriate library.
    - **Delete**: Use the system's `DeleteFile` tool or `rm` command.

## Usage

When the user asks to perform an operation on a document:

1.  Identify the file type and the specific operation (Read, Write, Modify, Delete).
2.  If it's a simple text file, use standard file tools (`Read`, `Write`).
3.  If it's a binary format (DOCX, PDF):
    - Verify if the required Python library is installed.
    - Generate a Python script to perform the task.
    - Run the script using `RunCommand`.
    - Report the result or content to the user.
