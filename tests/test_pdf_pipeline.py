# coding=utf-8

#  DataCatalog
#  Copyright (C) 2020  University of Luxembourg
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from pypdf import PdfReader

from datacatalog.converter.pdf_converter import merge, render_form, to_pdf
from datacatalog.exporter.rems_pdf_exporter import build_payload
from tests.base_test import BaseTest

FIXTURES = Path(__file__).parent / "fixtures"


class TestPdfPipeline(BaseTest):
    """Tests for the access request PDF pipeline (non-REMS steps).

    REMS connector methods (get_attachment, add_remark, etc.) are tested
    in tests/connector/test_rems_connector.py using requests_mock.
    """

    def test_build_payload(self):
        dataset = Mock(
            title="Genomic Dataset Alpha",
            id="DS-001",
            version="1.0",
            description="Whole-genome sequencing data",
            data_types=["Genomic"],
            access_mode="Controlled",
            platform="Test Platform",
            dataset_contact="normal user",
            dataset_email="normal@uni.lu",
            dataset_affiliation="University of Luxembourg",
            dataset_owner="LCSB",
            use_conditions=[
                {
                    "use_condition_note": "Research only",
                    "use_class": "DUO:0000007",
                    "use_class_label": "Disease specific research",
                    "use_condition_rule": "OBLIGATION",
                    "use_class_note": "",
                }
            ],
        )
        text_field = Mock(
            fieldid="purpose",
            fieldtype="text",
            fieldtitle={"en": "Research Purpose"},
            fieldcolumns=None,
        )
        attachment_field = Mock(
            fieldid="ethics_approval",
            fieldtype="attachment",
            fieldtitle={"en": "Ethics Approval"},
        )
        rems_form = Mock(fields=[text_field, attachment_field])

        form = Mock()
        form.use_condition_0 = Mock(data=True)
        form.license_1 = Mock(data=True)

        payload = build_payload(
            application_id=123,
            dataset=dataset,
            rems_form=rems_form,
            field_values={"purpose": "Cancer research", "ethics_approval": "42"},
            licenses=[Mock(id=1, localizations={"en": {"title": "CC-BY-4.0"}})],
            form=form,
            user=Mock(displayname="Jane Doe", email="jane@uni.lu"),
        )

        self.assertIn(42, payload["attachment_ids"])
        form_labels = [f["label"] for f in payload["form_fields"]]
        self.assertNotIn("Ethics Approval", form_labels)
        self.assertIn("Research Purpose", form_labels)
        self.assertTrue(payload["use_conditions"][0]["accepted"])
        self.assertEqual(payload["dataset_title"], "Genomic Dataset Alpha")
        self.assertEqual(payload["requester"]["name"], "Jane Doe")
        self.assertEqual(payload["requester"]["email"], "jane@uni.lu")

    def test_to_pdf_conversions(self):
        png_result = to_pdf((FIXTURES / "sample_circles.png").read_bytes(), "img.png")
        self.assertEqual(len(PdfReader(BytesIO(png_result)).pages), 1)

        docx_result = to_pdf((FIXTURES / "sample3.docx").read_bytes(), "doc.docx")
        self.assertGreaterEqual(len(PdfReader(BytesIO(docx_result)).pages), 1)

        pdf_bytes = (FIXTURES / "sample_document.pdf").read_bytes()
        self.assertEqual(to_pdf(pdf_bytes, "file.pdf"), pdf_bytes)

        self.assertIsNone(to_pdf(b"data", "file.xyz"))

    def test_render_form_and_merge(self):
        # render_form calls render_template, which triggers the
        # inject_access_handler context processor. That processor queries Solr
        # for dataset IDs, but the test Solr core does not exist here.
        with patch("datacatalog.get_access_handler", return_value=None):
            form_pdf = render_form(
                application_id=123,
                dataset_title="Test Dataset",
                requester={"name": "Jane Doe", "email": "jane@uni.lu"},
                form_fields=[
                    {"label": "Purpose", "value": "Cancer research", "type": "text", "columns": []}
                ],
                use_conditions=[
                    {
                        "use_condition_note": "Research only",
                        "use_class": "DUO:0000007",
                        "use_class_label": "Research use",
                        "use_condition_rule": "OBLIGATION",
                        "use_class_note": "",
                        "accepted": True,
                    },
                    {
                        "use_condition_note": "No redistribution",
                        "use_class": "DUO:0000044",
                        "use_class_label": "Population restrictions",
                        "use_condition_rule": "PROHIBITION",
                        "use_class_note": "",
                        "accepted": False,
                    },
                ],
                licenses=[{"title": "CC-BY-4.0", "accepted": True}],
                attachments=[
                    {"id": 10, "filename": "sample3.docx"},
                    {"id": 20, "filename": "sample_circles.png"},
                ],
            )

        full_text = "".join(p.extract_text() or "" for p in PdfReader(BytesIO(form_pdf)).pages)
        self.assertIn("Test Dataset", full_text)
        self.assertIn("sample3.docx", full_text)
        self.assertIn("Obligations", full_text)
        self.assertIn("Prohibitions", full_text)

        png_pdf = to_pdf((FIXTURES / "sample_circles.png").read_bytes(), "img.png")
        merged = merge([form_pdf, png_pdf])
        self.assertGreaterEqual(len(PdfReader(BytesIO(merged)).pages), 2)
