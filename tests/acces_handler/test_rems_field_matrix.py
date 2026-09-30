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

"""Matrix of every REMS form field type crossed with the value cases (#89).

Three directions are covered:

* REMS form definition -> WTForms field (``FieldBuilder.build_field``),
* submitted form data -> REMS draft field value (``validate`` + ``transform_value``,
  and the full ``RemsAccessHandler.apply`` save-draft payload),
* REMS field value -> access request PDF (``build_payload`` and the
  ``pdf/access_request.html`` template).
"""

import os
import re
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import (
    DateField,
    FieldList,
    FileField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.fields import EmailField, TelField
from wtforms.validators import DataRequired, Email, Length, Optional

from datacatalog import app, configure_solr_orm
from datacatalog.acces_handler.rems_handler import (
    FieldBuilder,
    RemsAccessHandler,
    UnsupportedFieldType,
)
from datacatalog.connector.rems_client import (
    CatalogueItem,
    Form,
    FormField as RemsFormField,
    Resource,
)
from datacatalog.converter.pdf_converter import render_form
from datacatalog.exporter.rems_pdf_exporter import build_payload, resolve_field_value
from datacatalog.forms import MultiCheckboxField
from datacatalog.models.dataset import Dataset

REMS_URL = "http://rems-mock-host"
FORM_ID = 3
APPLICATION_ID = 123
ATTACHMENT_ID = 7

OPTIONS = [
    {"key": "yes", "label": {"en": "Yes"}},
    {"key": "no", "label": {"en": "No"}},
]
COLUMNS = [
    {"key": "name", "label": {"en": "Name"}},
    {"key": "role", "label": {"en": "Role"}},
]
# Field types REMS offers that datacatalog has no builder for.
UNSUPPORTED_TYPES = ["ip-address", "unknown-type"]


@pytest.fixture(scope="module", autouse=True)
def configured_app():
    os.environ["DATACATALOG_ENV"] = "test"
    app.config.from_object("datacatalog.settings.TestConfig")
    configure_solr_orm(app)
    return app


def rems_field(fieldtype, optional=False, field_id="field", **extra):
    definition = {
        "field/id": field_id,
        "field/type": fieldtype,
        "field/title": {"en": f"{fieldtype} title"},
        "field/optional": optional,
    }
    if fieldtype in ("option", "multiselect"):
        definition["field/options"] = OPTIONS
    if fieldtype == "table":
        definition["field/columns"] = COLUMNS
    definition.update(extra)
    return RemsFormField(**definition)


def pdf_file(filename="ethics.pdf"):
    return (BytesIO(b"%PDF-1.4 content"), filename)


# ---------------------------------------------------------------------------
# REMS form definition -> WTForms field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fieldtype, expected_class, submits_value",
    [
        ("text", StringField, True),
        ("description", StringField, True),
        ("texta", TextAreaField, True),
        ("email", EmailField, True),
        ("phone-number", TelField, True),
        ("date", DateField, True),
        ("option", SelectField, True),
        ("multiselect", MultiCheckboxField, True),
        ("table", FieldList, True),
        ("attachment", FileField, True),
        ("label", StringField, False),
        ("header", StringField, False),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
@pytest.mark.parametrize("optional", [False, True], ids=["required", "optional"])
def test_definition_builds_wtforms_field(
    fieldtype, expected_class, submits_value, optional
):
    builder = FieldBuilder.build_field_builder(rems_field(fieldtype, optional))
    unbound_field = builder.build()

    assert unbound_field.field_class is expected_class
    assert builder.submits_value() is submits_value
    if fieldtype == "table":
        # validators live on the column sub-fields, checked below
        return
    validator_types = [type(v) for v in unbound_field.kwargs["validators"]]
    if not submits_value:
        assert validator_types == []
        assert unbound_field.kwargs["render_kw"] == {fieldtype: True}
        return
    assert (Optional if optional else DataRequired) in validator_types
    assert (DataRequired if optional else Optional) not in validator_types
    if fieldtype == "email":
        assert Email in validator_types
    if fieldtype == "attachment":
        assert FileAllowed in validator_types
    if fieldtype == "date":
        assert unbound_field.kwargs["render_kw"]["placeholder"] == "YYYY-MM-DD"
    if fieldtype in ("option", "multiselect"):
        assert unbound_field.kwargs["choices"] == [("yes", "Yes"), ("no", "No")]


@pytest.mark.parametrize(
    "extra, expected_validator_types, expected_render_kw",
    [
        ({}, [DataRequired], {}),
        ({"field/max-length": 5}, [DataRequired, Length], {}),
        (
            {"field/placeholder": {"en": "Type here"}},
            [DataRequired],
            {"placeholder": "Type here"},
        ),
        ({"field/placeholder": {"en": ""}}, [DataRequired], {}),
    ],
    ids=["plain", "max-length", "placeholder", "blank-placeholder"],
)
def test_definition_text_attributes(
    extra, expected_validator_types, expected_render_kw
):
    unbound_field = FieldBuilder.build_field(rems_field("text", **extra))
    assert [
        type(v) for v in unbound_field.kwargs["validators"]
    ] == expected_validator_types
    assert unbound_field.kwargs["render_kw"] == expected_render_kw


@pytest.mark.parametrize("fieldtype", UNSUPPORTED_TYPES)
def test_definition_unsupported_type_raises(fieldtype):
    with pytest.raises(UnsupportedFieldType):
        FieldBuilder.build_field(rems_field(fieldtype))


# ---------------------------------------------------------------------------
# Submitted form data -> REMS draft field value
# ---------------------------------------------------------------------------

MISSING = object()  # the key is not in the submitted data at all


def case(case_id, *values):
    """One matrix row: field type, optional, extra definition, submitted value,
    expected validity and expected REMS value."""
    return pytest.param(*values, id=case_id)


SUBMISSION_CASES = [
    # text / description / texta share the plain string behaviour
    case("text-missing-required", "text", False, {}, MISSING, False, ""),
    case("text-missing-optional", "text", True, {}, MISSING, True, ""),
    case("text-empty-required", "text", False, {}, "", False, ""),
    case("text-empty-optional", "text", True, {}, "", True, ""),
    case("text-whitespace-required", "text", False, {}, "   ", False, "   "),
    case("text-valid", "text", False, {}, "Cancer research", True, "Cancer research"),
    case("text-unicode", "text", False, {}, "Études ü 日本", True, "Études ü 日本"),
    case(
        "text-at-max-length",
        "text",
        False,
        {"field/max-length": 5},
        "abcde",
        True,
        "abcde",
    ),
    case(
        "text-over-max-length",
        "text",
        False,
        {"field/max-length": 5},
        "abcdef",
        False,
        "abcdef",
    ),
    case(
        "description-valid", "description", False, {}, "My project", True, "My project"
    ),
    case("description-empty-optional", "description", True, {}, "", True, ""),
    case(
        "texta-multiline", "texta", False, {}, "line 1\nline 2", True, "line 1\nline 2"
    ),
    case("texta-empty-optional", "texta", True, {}, "", True, ""),
    case("texta-empty-required", "texta", False, {}, "", False, ""),
    # phone-number
    case(
        "phone-number-valid",
        "phone-number",
        False,
        {},
        "+352 12 34 56",
        True,
        "+352 12 34 56",
    ),
    case("phone-number-empty-optional", "phone-number", True, {}, "", True, ""),
    case("phone-number-empty-required", "phone-number", False, {}, "", False, ""),
    # email
    case("email-valid", "email", False, {}, "jane@uni.lu", True, "jane@uni.lu"),
    case("email-invalid", "email", False, {}, "not-an-email", False, "not-an-email"),
    case(
        "email-invalid-optional",
        "email",
        True,
        {},
        "not-an-email",
        False,
        "not-an-email",
    ),
    case("email-empty-optional", "email", True, {}, "", True, ""),
    case("email-empty-required", "email", False, {}, "", False, ""),
    # date
    case("date-valid", "date", False, {}, "2026-09-28", True, "2026-09-28"),
    case("date-wrong-format", "date", False, {}, "28/09/2026", False, ""),
    case("date-impossible", "date", False, {}, "2026-02-30", False, ""),
    case("date-empty-optional", "date", True, {}, "", True, ""),
    case("date-empty-required", "date", False, {}, "", False, ""),
    case("date-missing-optional", "date", True, {}, MISSING, True, ""),
    # option
    case("option-valid", "option", False, {}, "yes", True, "yes"),
    case("option-unknown-key", "option", False, {}, "maybe", False, "maybe"),
    case("option-label-instead-of-key", "option", False, {}, "Yes", False, "Yes"),
    case("option-missing-required", "option", False, {}, MISSING, False, ""),
    case("option-missing-optional", "option", True, {}, MISSING, True, ""),
    case("option-empty-optional", "option", True, {}, "", True, ""),
    case("option-empty-required", "option", False, {}, "", False, ""),
    # multiselect
    case("multiselect-one", "multiselect", False, {}, ["yes"], True, "yes"),
    case(
        "multiselect-several", "multiselect", False, {}, ["yes", "no"], True, "yes no"
    ),
    case(
        "multiselect-unknown-key",
        "multiselect",
        False,
        {},
        ["yes", "maybe"],
        False,
        "yes maybe",
    ),
    case("multiselect-missing-required", "multiselect", False, {}, MISSING, False, ""),
    case("multiselect-missing-optional", "multiselect", True, {}, MISSING, True, ""),
    # table: the value is a list of rows, keyed "<field>-<row>-<column>"
    case(
        "table-one-row",
        "table",
        False,
        {},
        [{"name": "Jane", "role": "PI"}],
        True,
        [[{"column": "name", "value": "Jane"}, {"column": "role", "value": "PI"}]],
    ),
    case(
        "table-two-rows",
        "table",
        False,
        {},
        [{"name": "Jane", "role": "PI"}, {"name": "John", "role": "Analyst"}],
        True,
        [
            [{"column": "name", "value": "Jane"}, {"column": "role", "value": "PI"}],
            [
                {"column": "name", "value": "John"},
                {"column": "role", "value": "Analyst"},
            ],
        ],
    ),
    case(
        "table-blank-cell-optional",
        "table",
        True,
        {},
        [{"name": "", "role": "PI"}],
        True,
        [[{"column": "role", "value": "PI"}]],
    ),
    case(
        "table-blank-cell-required",
        "table",
        False,
        {},
        [{"name": "", "role": "PI"}],
        False,
        [[{"column": "role", "value": "PI"}]],
    ),
    case(
        "table-blank-row-optional",
        "table",
        True,
        {},
        [{"name": "", "role": ""}],
        True,
        [[]],
    ),
    case("table-missing-optional", "table", True, {}, MISSING, True, [[]]),
    case("table-missing-required", "table", False, {}, MISSING, False, [[]]),
    # attachment: the browser always sends the file part, empty when no file is chosen
    case(
        "attachment-valid", "attachment", False, {}, pdf_file, True, str(ATTACHMENT_ID)
    ),
    case("attachment-no-file-optional", "attachment", True, {}, "no-file", True, ""),
    case("attachment-no-file-required", "attachment", False, {}, "no-file", False, ""),
    case(
        "attachment-bad-extension",
        "attachment",
        False,
        {},
        lambda: pdf_file("run.exe"),
        False,
        str(ATTACHMENT_ID),
    ),
]


def submitted_data(value):
    """Build the multipart POST body the browser would send for ``field``."""
    data = {"submit": "Send"}
    if value is MISSING:
        return data
    if value == "no-file":
        data["field"] = (BytesIO(b""), "")
    elif callable(value):
        data["field"] = value()
    elif isinstance(value, list) and value and isinstance(value[0], dict):
        for index, row in enumerate(value):
            for column, cell in row.items():
                data[f"field-{index}-{column}"] = cell
    else:
        data["field"] = value
    return data


@pytest.mark.parametrize(
    "fieldtype, optional, extra, value, expected_valid, expected_rems_value",
    SUBMISSION_CASES,
)
def test_submission_to_rems_value(
    fieldtype, optional, extra, value, expected_valid, expected_rems_value
):
    builder = FieldBuilder.build_field_builder(rems_field(fieldtype, optional, **extra))

    class SubmittedForm(FlaskForm):
        pass

    SubmittedForm.field = builder.build()
    connector = MagicMock()
    connector.add_attachment.return_value = ATTACHMENT_ID
    with app.test_request_context(
        method="POST", data=submitted_data(value), content_type="multipart/form-data"
    ):
        form = SubmittedForm()
        is_valid = form.validate()
        rems_value = builder.transform_value(form.field.data, connector, APPLICATION_ID)

    assert is_valid is expected_valid, form.errors
    assert rems_value == expected_rems_value


@pytest.mark.parametrize(
    "fieldtype",
    ["text", "description", "texta", "email", "date", "option", "multiselect", "table"],
)
def test_none_value_becomes_empty_string(fieldtype):
    builder = FieldBuilder.build_field_builder(rems_field(fieldtype))
    assert builder.transform_value(None) == ""


@pytest.mark.parametrize(
    "value, expected",
    [
        ("not a list", ""),
        ([], []),
        (["not a dict", {"name": "Jane"}], [[{"column": "name", "value": "Jane"}]]),
        (
            [{"name": "Jane", "csrf_token": "token"}],
            [[{"column": "name", "value": "Jane"}]],
        ),
        ([{"name": None, "role": "PI"}], [[{"column": "role", "value": "PI"}]]),
    ],
    ids=[
        "string",
        "no-rows",
        "non-dict-row-skipped",
        "csrf-token-dropped",
        "none-cell-dropped",
    ],
)
def test_table_transform_edge_values(value, expected):
    builder = FieldBuilder.build_field_builder(rems_field("table"))
    assert builder.transform_value(value) == expected


# ---------------------------------------------------------------------------
# Full apply(): every field type in one REMS form -> save-draft payload
# ---------------------------------------------------------------------------

ORGANIZATION = {
    "organization/id": "test-org",
    "organization/short-name": {"en": "Test Org"},
    "organization/name": {"en": "Test Organization"},
}

# (field type, optional, submitted value, REMS value in the save-draft payload)
APPLY_FIELDS = [
    ("text", False, "Cancer research", "Cancer research"),
    ("description", True, "", ""),
    ("texta", False, "line 1\nline 2", "line 1\nline 2"),
    ("email", False, "jane@uni.lu", "jane@uni.lu"),
    ("phone-number", False, "+352 12 34 56", "+352 12 34 56"),
    ("date", False, "2026-09-28", "2026-09-28"),
    ("option", False, "no", "no"),
    ("multiselect", False, ["yes", "no"], "yes no"),
    (
        "table",
        True,
        [{"name": "Jane", "role": ""}, {"name": "John", "role": "PI"}],
        [
            [{"column": "name", "value": "Jane"}],
            [{"column": "name", "value": "John"}, {"column": "role", "value": "PI"}],
        ],
    ),
    ("attachment", False, pdf_file, str(ATTACHMENT_ID)),
    ("label", True, MISSING, None),
    ("header", True, MISSING, None),
]


def mock_rems(mocker, dataset, fields):
    catalogue_item = CatalogueItem(
        id=1,
        resid=dataset.id,
        formid=FORM_ID,
        wfid=3,
        **{"resource-id": 1},
        archived=False,
        localizations={"en": {"title": "Test Dataset"}},
        start="2023-01-01T00:00:00Z",
        organization={"organization/id": "test-org"},
        expired=False,
        end=None,
        enabled=True,
    )
    resource = Resource(
        id=1,
        resid=dataset.id,
        enabled=True,
        archived=False,
        organization=ORGANIZATION,
        licenses=[],
        **{"resource/duo": {}},
    )
    form = Form(
        **{"form/id": FORM_ID},
        **{"form/internal-name": "test-form"},
        **{"form/title": "Test Form"},
        **{"form/external-title": {"en": "Test Form Title"}},
        archived=False,
        enabled=True,
        organization=ORGANIZATION,
        **{"form/fields": [f.model_dump(by_alias=True) for f in fields]},
    )
    mocker.get(
        f"{REMS_URL}/api/catalogue-items",
        json=[catalogue_item.model_dump(by_alias=True)],
    )
    mocker.get(f"{REMS_URL}/api/resources/1", json=resource.model_dump(by_alias=True))
    mocker.get(f"{REMS_URL}/api/forms/{FORM_ID}", json=form.model_dump(by_alias=True))
    mocker.post(
        f"{REMS_URL}/api/applications/create",
        json={"success": True, "application-id": APPLICATION_ID},
    )
    mocker.post(
        f"{REMS_URL}/api/applications/add-attachment",
        json={"success": True, "id": ATTACHMENT_ID},
    )
    for action in ("save-draft", "accept-licenses", "submit"):
        mocker.post(f"{REMS_URL}/api/applications/{action}", json={"success": True})


def rems_dataset():
    dataset = Dataset("Matrix dataset")
    dataset.e2e = True
    dataset.form_id = FORM_ID
    return dataset


def submit_through_handler(fields, data):
    """Build the form with create_form, validate it and apply it like the controller."""
    dataset = rems_dataset()
    with requests_mock.Mocker() as mocker:
        mock_rems(mocker, dataset, fields)
        with app.test_request_context(
            method="POST", data=data, content_type="multipart/form-data"
        ):
            handler = RemsAccessHandler(
                current_user, "api-user", "api-key", REMS_URL, 3, False
            )
            form = handler.create_form(dataset, None)
            assert form.validate(), form.errors
            handler.apply(dataset, form)
        save_draft = next(
            r
            for r in mocker.request_history
            if r.url.endswith("/api/applications/save-draft")
        )
        return save_draft.json()


def test_apply_every_field_type_save_draft_payload():
    fields = []
    data = {"submit": "Send"}
    for fieldtype, optional, value, _ in APPLY_FIELDS:
        fields.append(rems_field(fieldtype, optional, field_id=fieldtype))
        for key, item in submitted_data(value).items():
            data[key.replace("field", fieldtype, 1)] = item

    payload = submit_through_handler(fields, data)

    assert payload == {
        "application-id": APPLICATION_ID,
        "field-values": [
            {"form": FORM_ID, "field": fieldtype, "value": rems_value}
            for fieldtype, _, _, rems_value in APPLY_FIELDS
            if rems_value is not None  # label and header submit nothing
        ],
    }


@pytest.mark.parametrize("fieldtype", UNSUPPORTED_TYPES)
def test_create_form_skips_unsupported_type(fieldtype):
    dataset = rems_dataset()
    fields = [
        rems_field("text", field_id="text"),
        rems_field(fieldtype, field_id="unsupported"),
    ]
    with requests_mock.Mocker() as mocker, app.test_request_context():
        mock_rems(mocker, dataset, fields)
        handler = RemsAccessHandler(
            current_user, "api-user", "api-key", REMS_URL, 3, False
        )
        form = handler.create_form(dataset, None)
    assert "text" in form._fields
    assert "unsupported" not in form._fields


@pytest.mark.parametrize("fieldtype", UNSUPPORTED_TYPES)
def test_apply_skips_unsupported_type(fieldtype):
    fields = [
        rems_field("text", field_id="text"),
        rems_field(fieldtype, True, field_id="unsupported"),
    ]
    payload = submit_through_handler(fields, {"text": "value", "submit": "Send"})
    assert payload["field-values"] == [
        {"form": FORM_ID, "field": "text", "value": "value"}
    ]


# ---------------------------------------------------------------------------
# REMS field value -> access request PDF
# ---------------------------------------------------------------------------

TABLE_ROWS = [
    [{"column": "name", "value": "Jane"}, {"column": "role", "value": "PI"}],
    [{"column": "name", "value": "John"}],
]


@pytest.mark.parametrize(
    "fieldtype, rems_value, expected",
    [
        ("text", "Cancer research", "Cancer research"),
        ("text", "", ""),
        ("description", "My project", "My project"),
        ("texta", "line 1\nline 2", "line 1\nline 2"),
        ("email", "jane@uni.lu", "jane@uni.lu"),
        ("date", "2026-09-28", "2026-09-28"),
        ("date", "", ""),
        ("option", "yes", "Yes"),
        ("option", "maybe", "maybe"),
        ("option", "", ""),
        ("multiselect", "yes no", "Yes, No"),
        ("multiselect", "no maybe", "No, maybe"),
        ("multiselect", "", ""),
        ("table", TABLE_ROWS, [["Jane", "PI"], ["John", ""]]),
        ("table", [[]], [["", ""]]),
        ("table", [], []),
        ("table", "", ""),
    ],
    ids=[
        "text-valid",
        "text-empty",
        "description-valid",
        "texta-multiline",
        "email-valid",
        "date-valid",
        "date-empty",
        "option-key-to-label",
        "option-unknown-key",
        "option-empty",
        "multiselect-keys-to-labels",
        "multiselect-unknown-key",
        "multiselect-empty",
        "table-rows",
        "table-blank-row",
        "table-no-rows",
        "table-not-a-list",
    ],
)
def test_pdf_resolves_field_value(fieldtype, rems_value, expected):
    assert resolve_field_value(rems_field(fieldtype), rems_value) == expected


def test_pdf_payload_every_field_type():
    fields = [
        rems_field(fieldtype, field_id=fieldtype) for fieldtype, *_ in APPLY_FIELDS
    ]
    field_values = {
        fieldtype: rems_value
        for fieldtype, _, _, rems_value in APPLY_FIELDS
        if rems_value is not None
    }
    payload = build_payload(
        application_id=APPLICATION_ID,
        dataset=MagicMock(use_conditions=[]),
        rems_form=MagicMock(fields=fields),
        field_values=field_values,
        licenses=[],
        form=MagicMock(),
        user=MagicMock(displayname="Jane Doe", email="jane@uni.lu"),
    )

    assert payload["attachment_ids"] == [ATTACHMENT_ID]
    rendered = {field["type"]: field for field in payload["form_fields"]}
    # attachments go to attachment_ids, label and header have no value
    assert set(rendered) == set(field_values) - {"attachment"}
    assert rendered["option"]["value"] == "No"
    assert rendered["multiselect"]["value"] == "Yes, No"
    assert rendered["table"]["value"] == [["Jane", ""], ["John", "PI"]]
    assert rendered["table"]["columns"] == ["Name", "Role"]
    assert rendered["text"]["columns"] == []


def rendered_pdf_html(form_fields):
    """Return the HTML render_form passes to WeasyPrint."""
    with (
        patch("datacatalog.get_access_handler", return_value=None),
        patch("datacatalog.converter.pdf_converter.HTML") as html_class,
    ):
        with app.test_request_context():
            render_form(
                application_id=APPLICATION_ID,
                dataset_title="Matrix dataset",
                requester={"name": "Jane Doe", "email": "jane@uni.lu"},
                form_fields=form_fields,
            )
    return " ".join(html_class.call_args.kwargs["string"].split())


def table_cells(html):
    """(label, value) pairs of the table-field rows in the Form Data section."""
    form_data_section = html.split("Form Data", 1)[1]
    return re.findall(
        r'<td class="label">([^<]*)</td> <td class="value wrap[^"]*">([^<]*)</td>',
        form_data_section,
    )


@pytest.mark.parametrize(
    "value, expected_text",
    [
        ("Cancer research", "Cancer research"),
        ("", "Not provided"),
        (None, "Not provided"),
    ],
    ids=["valid", "empty", "none"],
)
def test_pdf_template_renders_simple_value(value, expected_text):
    html = rendered_pdf_html(
        [{"label": "Purpose", "value": value, "type": "text", "columns": []}]
    )
    form_data_section = html.split("Form Data", 1)[1]
    assert re.search(
        rf'Purpose</td> <td class="value wrap[^"]*">{expected_text}</td>',
        form_data_section,
    )


@pytest.mark.parametrize(
    "rows, expected_cells",
    [
        pytest.param(
            [["Jane", "PI"]],
            [("Name", "Jane"), ("Role", "PI")],
            id="full-row",
        ),
        pytest.param(
            [["Jane", "PI"], ["John", "Analyst"]],
            [("Name", "Jane"), ("Role", "PI"), ("Name", "John"), ("Role", "Analyst")],
            id="two-rows",
        ),
        pytest.param(
            [["Jane"]],
            [("Name", "Jane"), ("Role", "Not provided")],
            id="blank-last-cell",
        ),
        pytest.param(
            [[]], [("Name", "Not provided"), ("Role", "Not provided")], id="blank-row"
        ),
        pytest.param([], [], id="no-rows"),
    ],
)
def test_pdf_template_renders_table_rows(rows, expected_cells):
    html = rendered_pdf_html(
        [{"label": "Team", "value": rows, "type": "table", "columns": ["Name", "Role"]}]
    )
    assert table_cells(html) == expected_cells


def test_pdf_table_blank_first_cell_keeps_columns_aligned():
    builder = FieldBuilder.build_field_builder(rems_field("table", True))
    rems_value = builder.transform_value([{"name": "", "role": "PI"}])
    rows = resolve_field_value(rems_field("table", True), rems_value)
    html = rendered_pdf_html(
        [{"label": "Team", "value": rows, "type": "table", "columns": ["Name", "Role"]}]
    )
    assert table_cells(html) == [("Name", "Not provided"), ("Role", "PI")]
