import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery import shared_task

from flask import current_app
from datacatalog.connector.rems_connector import RemsConnector

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


@shared_task(bind=True, ignore_result=True, max_retries=1, acks_late=True)
def attach_request_pdf(
    self,
    application_id: int,
    dataset_title: str,
    requester: Dict[str, str],
    form_fields: List[Dict[str, Any]],
    attachment_ids: List[int],
    dataset_metadata: Optional[Dict[str, Any]] = None,
    use_conditions: Optional[List[Dict[str, Any]]] = None,
    licenses: Optional[List[Dict[str, Any]]] = None,
):
    logger.info("Generating request PDF for application %s", application_id)

    # Import lazily so missing PDF native libraries do not break app startup.
    from datacatalog.converter.pdf_converter import to_pdf, merge, render_form

    connector = None
    tmp_path = None
    try:
        connector = rems_connector()

        attachments = []
        if attachment_ids:
            application = connector.get_application(application_id)
            attachments_by_id = {a.id: a for a in application.attachments}
            attachments = [
                (att_id, attachments_by_id[att_id].filename)
                for att_id in attachment_ids
            ]

        form_pdf = render_form(
            application_id=application_id,
            dataset_title=dataset_title,
            dataset_metadata=dataset_metadata,
            requester=requester,
            form_fields=form_fields,
            use_conditions=use_conditions,
            licenses=licenses,
            attachments=[
                {"id": attachment_id, "filename": filename}
                for attachment_id, filename in attachments
            ],
        )
        parts = [form_pdf]

        for attachment_id, filename in attachments:
            content = connector.get_attachment(attachment_id)
            converted = to_pdf(content, filename)
            if converted:
                parts.append(converted)

        final_pdf = merge(parts)

        tmp_path = (
            Path(tempfile.gettempdir())
            / f"data_access_request_summary_{application_id}.pdf"
        )
        tmp_path.write_bytes(final_pdf)

        pdf_attachment_id = connector.add_attachment(application_id, str(tmp_path))
        connector.add_remark(
            application_id=application_id,
            comment="Access request PDF attached",
            attachments=[{"attachment/id": pdf_attachment_id}],
            public=False,
        )
        logger.info("Request PDF attached to application %s", application_id)
    except Exception as exc:
        retries = self.request.retries
        if retries < self.max_retries:
            logger.warning(
                "Retrying request PDF generation for application %s (%s/%s)",
                application_id,
                retries + 1,
                self.max_retries,
                exc_info=True,
            )
            raise self.retry(exc=exc, countdown=5)

        logger.exception(
            "Request PDF generation failed for application %s after %s retries",
            application_id,
            retries,
        )
        if connector:
            connector.add_remark(
                application_id=application_id,
                comment="Access request PDF generation failed",
                public=False,
            )
        raise
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
