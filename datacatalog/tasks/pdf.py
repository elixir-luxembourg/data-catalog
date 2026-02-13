import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery import shared_task

from flask import current_app
from datacatalog.connector.rems_connector import RemsConnector
from datacatalog.converter.pdf_converter import to_pdf, merge, render_form

logger = logging.getLogger(__name__)


def rems_connector():
    return RemsConnector(
        api_username=current_app.config["REMS_API_USER"],
        api_key=current_app.config["REMS_API_KEY"],
        host=current_app.config["REMS_URL"],
        workflow_id=current_app.config["REMS_WORKFLOW_ID"],
        verify_ssl=current_app.config.get("REMS_VERIFY_SSL", False),
        admin_user=current_app.config["REMS_API_USER"],
    )


@shared_task(ignore_result=True)
def attach_request_pdf(
    application_id: int,
    dataset_title: str,
    requester: Dict[str, str],
    form_fields: List[Dict[str, Any]],
    attachment_ids: List[int],
    dataset_metadata: Optional[Dict[str, Any]] = None,
    use_conditions: Optional[List[Dict[str, Any]]] = None,
    licenses: Optional[List[Dict[str, Any]]] = None,
):
    logger.info(f"Generating request PDF for application {application_id}")

    connector = rems_connector()

    attachments_info = []
    attachments_by_id = {}
    if attachment_ids:
        application = connector.get_application(application_id)
        attachments_by_id = {a.id: a for a in application.attachments}
        for att_id in attachment_ids:
            attachments_info.append(
                {
                    "id": att_id,
                    "filename": attachments_by_id[att_id].filename,
                }
            )

    try:
        form_pdf = render_form(
            application_id=application_id,
            dataset_title=dataset_title,
            dataset_metadata=dataset_metadata,
            requester=requester,
            form_fields=form_fields,
            use_conditions=use_conditions,
            licenses=licenses,
            attachments=attachments_info,
        )
        parts = [form_pdf]

        for att_id in attachment_ids:
            content = connector.get_attachment(att_id)
            converted = to_pdf(content, attachments_by_id[att_id].filename)
            if converted:
                parts.append(converted)

        final_pdf = merge(parts)
    except Exception:
        logger.exception("Request PDF generation failed for application %s", application_id)
        connector.add_remark(
            application_id=application_id,
            comment="Access request PDF generation failed",
            public=False,
        )
        raise

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(final_pdf)
        tmp_path = tmp.name

    pdf_attachment_id = connector.add_attachment(application_id, tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    connector.add_remark(
        application_id=application_id,
        comment="Access request PDF attached",
        attachments=[{"attachment/id": pdf_attachment_id}],
        public=False,
    )
    logger.info(f"Request PDF attached to application {application_id}")
