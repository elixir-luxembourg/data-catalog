# Manual testing checklist

Use this checklist for every merge request to `main`.

The merge request author identifies the applicable conditional sections.

Record: environment URL, commit SHA, tester/date, browser, test account/role, services checked, result, and defect links.

## Basic checks

- [ ] Confirm the deployed environment contains the expected commit and the home page loads in a fresh browser session.
- [ ] Complete the affected user workflow, including its success state and one expected validation, empty, or error state.
- [ ] When affected, exercise search/autocomplete, filters, pagination, attachments, and download actions through the interface.
- [ ] Confirm the changed page is usable at desktop and mobile widths, with no unexpected console, network, or server errors.
- [ ] For a visual change, compare the affected page with the approved screenshot or last known-good `main` version.

## Run when affected

### OIDC

- [ ] Sign in and out through OIDC; confirm the user returns to the catalogue with the expected identity.
- [ ] With a user who already has dataset access, sign in and confirm the dataset appears under **Accessible datasets** in **My Applications**.

### DAISY import, Solr sync and REMS export

- [ ] Run the affected import or synchronisation and confirm the expected records appear in Search.
- [ ] Check an imported record's essential metadata, links, and status, including a deprecated or incomplete record when relevant.
- [ ] After a DAISY dataset import, or when REMS client/export code changes, run `flask export entities Rems dataset` and confirm the affected datasets are present and correct in REMS.

### Access request pipeline: REMS, DAISY, and download handler

Run this end-to-end flow with a requester account and a REMS steward account when access requests, REMS, DAISY, or the `DOWNLOADS_HANDLER` configuration change.

- [ ] As the requester, submit an access request for a dataset in Data Catalog.
- [ ] In **My Applications**, confirm the request appears with the expected submitted status.
- [ ] For a dataset with PDF generation enabled, as the REMS steward confirm a generated PDF report is attached to this application.
- [ ] As the steward, approve the request in REMS.
- [ ] Confirm the approved request/access is present in DAISY.
- [ ] As the requester, sign in again, confirm the dataset is listed under **Accessible datasets** in **My Applications**, then open its download link and confirm it reaches the expected resource.

### Solr schema

- [ ] For schema changes, run `flask indexer clear all` and `flask indexer commit`, then complete the reinitialisation, import, and extension sequence in [update_data.sh](update_data.sh) and confirm the affected entities can be found in Search.

## Result

- [ ] Attach evidence for failures or approved visual changes, and report defects with the affected URL/endpoint, user role, test data, expected result, and actual result.
- [ ] Mark the merge request manually tested only when all applicable checks pass or deviations are explicitly accepted.
