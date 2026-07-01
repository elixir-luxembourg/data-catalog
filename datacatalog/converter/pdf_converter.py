import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import render_template
from PIL import Image
from pypdf import PdfReader, PdfWriter
from weasyprint import HTML
from weasyprint.fonts import FontConfiguration

logger = logging.getLogger(__name__)


def image_to_pdf(data: bytes) -> bytes:
    img = Image.open(BytesIO(data))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    output = BytesIO()
    img.save(output, format="PDF")
    return output.getvalue()


def docx_to_pdf(data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "input.docx"
        docx_path.write_bytes(data)

        try:
            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmpdir,
                    str(docx_path),
                ],
                capture_output=True,
                timeout=60,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "LibreOffice is not installed. "
                "Install libreoffice-writer to enable DOCX-to-PDF conversion."
            )

        if result.returncode != 0:
            raise RuntimeError(f"DOCX conversion failed: {result.stderr.decode()}")

        return (Path(tmpdir) / "input.pdf").read_bytes()


def to_pdf(content: bytes, filename: str) -> Optional[bytes]:
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return content
    elif ext in (".jpg", ".jpeg", ".png"):
        return image_to_pdf(content)
    elif ext in (".docx", ".doc"):
        return docx_to_pdf(content)
    else:
        logger.warning(f"Unsupported file type: {ext}")
        return None


def render_form(
    application_id: int,
    dataset_title: str,
    requester: Dict[str, str],
    form_fields: List[Dict[str, Any]],
    dataset_metadata: Optional[Dict[str, Any]] = None,
    use_conditions: Optional[List[Dict[str, Any]]] = None,
    licenses: Optional[List[Dict[str, Any]]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    html = render_template(
        "pdf/access_request.html",
        application_id=application_id,
        dataset_title=dataset_title,
        dataset=dataset_metadata or {},
        requester=requester,
        form_fields=form_fields,
        use_conditions=use_conditions or [],
        licenses=licenses or [],
        attachments=attachments or [],
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    doc = HTML(string=html)
    return doc.write_pdf(font_config=FontConfiguration())


def merge(pages: List[bytes]) -> bytes:
    writer = PdfWriter()
    for content in pages:
        reader = PdfReader(BytesIO(content))
        for page in reader.pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
