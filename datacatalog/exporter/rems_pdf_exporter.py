import logging

from datacatalog.tasks.pdf import attach_request_pdf

logger = logging.getLogger(__name__)

USE_CONDITION_KEYS = (
    "use_condition_note",
    "use_class",
    "use_class_label",
    "use_condition_rule",
    "use_class_note",
)


def build_payload(application_id, dataset, rems_form, field_values, licenses, form, user):
    form_fields = []
    attachment_ids = []

    for field in rems_form.fields:
        field_id = field.fieldid
        if field_id not in field_values:
            continue

        if field.fieldtype == "attachment":
            value = field_values[field_id]
            if value:
                attachment_ids.append(int(value))
            continue

        value = field_values[field_id]
        label = resolve_field_value(field, value)

        form_fields.append(
            {
                "label": field.fieldtitle.get("en", field_id),
                "value": label,
                "type": field.fieldtype,
                "columns": [
                    c.get("label", {}).get("en") or c.get("key")
                    for c in (field.fieldcolumns or [])
                ],
            }
        )

    accepted_licenses = []
    for license in licenses:
        form_field = getattr(form, f"license_{license.id}", None)
        accepted_licenses.append({
            "title": license.localizations["en"]["title"],
            "accepted": form_field.data if form_field else False,
        })

    return {
        "application_id": application_id,
        "dataset_title": dataset.title,
        "dataset_metadata": {
            "id": dataset.id,
            "version": dataset.version,
            "description": dataset.description,
            "data_types": dataset.data_types,
            "access_mode": dataset.access_mode,
            "platform": dataset.platform,
            "contact": dataset.dataset_contact,
            "email": dataset.dataset_email,
            "affiliation": dataset.dataset_affiliation,
            "owner": dataset.dataset_owner,
        },
        "requester": {
            "name": user.displayname,
            "email": user.email,
            "organization": getattr(user, "organization", None),
        },
        "form_fields": form_fields,
        "attachment_ids": attachment_ids,
        "use_conditions": collect_use_conditions(dataset, form),
        "licenses": accepted_licenses,
    }


def resolve_field_value(field, value):
    if field.fieldtype == "option" and field.fieldoptions:
        for opt in field.fieldoptions:
            if opt.key == value:
                return opt.label.get("en", value)
        return value

    if field.fieldtype == "multiselect" and field.fieldoptions:
        labels = {opt.key: opt.label.get("en", opt.key) for opt in field.fieldoptions}
        keys = value.split() if isinstance(value, str) else []
        return ", ".join(labels.get(key, key) for key in keys)

    if field.fieldtype == "table" and isinstance(value, list):
        return [
            [cell.get("value") for cell in row]
            for row in value
            if isinstance(row, list)
        ]

    return value


def collect_use_conditions(dataset, form):
    result = []
    for index, condition in enumerate(dataset.use_conditions or []):
        form_field = getattr(form, f"use_condition_{index}", None)
        entry = {key: condition.get(key, "") for key in USE_CONDITION_KEYS}
        entry["accepted"] = form_field.data if form_field else False
        result.append(entry)
    return result


def dispatch(application_id, dataset, rems_form, field_values, licenses, form, user):
    payload = build_payload(
        application_id=application_id,
        dataset=dataset,
        rems_form=rems_form,
        field_values=field_values,
        licenses=licenses,
        form=form,
        user=user,
    )
    attach_request_pdf.delay(**payload)
    logger.info(f"Queued request PDF for application {application_id}")
