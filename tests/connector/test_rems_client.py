import tempfile

import pytest
import requests

from datacatalog.connector.rems_client import (
    Resource,
    CreateResourceCommand,
    CreateResponse,
    AcceptLicensesCommand,
    SaveDraftCommand,
    CreateApplicationCommand,
    Form,
    CatalogueItem,
    Application,
    CreateApplicationResponse,
    SuccessResponse,
)


class TestRemsConnector:
    def test_create_user(
        self, rems_client, requests_mock, user_with_attributes_factory
    ):
        mock_response = user_with_attributes_factory.build()
        requests_mock.post(
            url=f"{rems_client.base_url}/api/users/create",
            json={"success": True},
        )

        user = rems_client.create_user(
            mock_response.user_id, mock_response.name, mock_response.email
        )

        assert user is True

    def test_create_user_http_error(self, rems_client, requests_mock):
        requests_mock.post(
            url=f"{rems_client.base_url}/api/users/create",
            status_code=400,
        )

        with pytest.raises(requests.exceptions.HTTPError) as e:
            rems_client.create_user("userid", "name", "email@email.com")

        assert e.value.response.status_code == 400

    def test_get_applications(self, rems_client, requests_mock, rems_application):
        mock_response = [rems_application for _ in range(3)]
        requests_mock.get(
            url=f"{rems_client.base_url}/api/applications",
            json=[
                app.model_dump(by_alias=True, exclude_unset=True)
                for app in mock_response
            ],
        )

        applications = rems_client.get_applications()

        assert isinstance(applications, list)
        assert len(applications) == 3
        for app in applications:
            assert isinstance(app, Application)
        assert applications[0].id == mock_response[0].id

    def test_get_applications_with_query(
        self, rems_client, requests_mock, rems_application
    ):
        application = rems_application
        requests_mock.get(
            url=f"{rems_client.base_url}/api/applications",
            json=[application.model_dump(by_alias=True, exclude_unset=True)],
        )

        applications = rems_client.get_applications(
            query=f'resource:"{application.resources[0].id}"'
        )

        assert isinstance(applications, list)
        assert len(applications) == 1
        for app in applications:
            assert isinstance(app, Application)
        assert applications[0].id == application.id

    def test_get_application(self, rems_client, requests_mock, rems_application):
        mock_response = rems_application
        application_id = mock_response.id
        requests_mock.get(
            url=f"{rems_client.base_url}/api/applications/{application_id}",
            json=mock_response.model_dump(by_alias=True, exclude_unset=True),
        )

        application = rems_client.get_application(application_id)

        assert isinstance(application, Application)
        assert application.id == mock_response.id

    def test_close_application(self, rems_client, requests_mock):
        application_id = 123
        requests_mock.post(
            url=f"{rems_client.base_url}/api/applications/close",
            json={"application-id": application_id},
        )

        rems_client.close_application(application_id)

        last_request = requests_mock.request_history[-1]
        assert last_request.method == "POST"
        assert last_request.json() == {"application-id": application_id}

    def test_get_my_applications(self, rems_client, requests_mock, rems_application):
        mock_response = [rems_application for _ in range(2)]
        requests_mock.get(
            url=f"{rems_client.base_url}/api/my-applications",
            json=[
                app.model_dump(by_alias=True, exclude_unset=True)
                for app in mock_response
            ],
        )

        applications = rems_client.get_my_applications()

        assert isinstance(applications, list)
        assert len(applications) == 2
        for app in applications:
            assert isinstance(app, Application)
        assert applications[0].id == mock_response[0].id

    def test_get_catalogue_item(
        self, rems_client, requests_mock, catalogue_item_factory
    ):
        mock_response = catalogue_item_factory.build()
        item_id = mock_response.id
        requests_mock.get(
            url=f"{rems_client.base_url}/api/catalogue-items/{item_id}",
            json=mock_response.model_dump(by_alias=True, exclude_unset=True),
        )

        catalogue_item = rems_client.get_catalogue_item(item_id)

        assert isinstance(catalogue_item, CatalogueItem)
        assert catalogue_item.id == mock_response.id

    def test_get_form(self, rems_client, requests_mock, form_factory):
        mock_response = form_factory.build()
        form_id = mock_response.id
        requests_mock.get(
            url=f"{rems_client.base_url}/api/forms/{form_id}",
            json=mock_response.model_dump(by_alias=True, exclude_unset=True),
        )

        form = rems_client.get_form(form_id)

        assert isinstance(form, Form)
        assert form.id == mock_response.id

    def test_create_application(
        self,
        rems_client,
        requests_mock,
        create_application_command_factory,
        create_application_response_factory,
    ):
        command: CreateApplicationCommand = create_application_command_factory.build()
        mock_application = create_application_response_factory.build()
        requests_mock.post(
            url=f"{rems_client.base_url}/api/applications/create",
            json=mock_application.model_dump(by_alias=True, exclude_unset=True),
        )

        application = rems_client.create_application(command.catalogue_item_ids)

        assert isinstance(application, CreateApplicationResponse)
        assert application.success == mock_application.success

    def test_save_draft(
        self,
        rems_client,
        requests_mock,
        save_draft_command_factory,
        success_response_factory,
    ):
        command: SaveDraftCommand = save_draft_command_factory.build()
        mock_application = success_response_factory.build()
        requests_mock.post(
            url=f"{rems_client.base_url}/api/applications/save-draft",
            json=mock_application.model_dump(by_alias=True, exclude_unset=True),
        )

        application = rems_client.save_draft(
            command.application_id, command.field_values
        )

        assert isinstance(application, SuccessResponse)
        assert application.success == mock_application.success

    def test_get_resource(self, rems_client, requests_mock, resource_factory):
        mock_response = resource_factory.build()
        resource_id = mock_response.id
        requests_mock.get(
            url=f"{rems_client.base_url}/api/resources/{resource_id}",
            json=mock_response.model_dump(by_alias=True, exclude_unset=True),
        )
        resource = rems_client.get_resource(resource_id)

        assert isinstance(resource, Resource)
        assert resource.id == mock_response.id

    def test_accept_licenses(
        self,
        rems_client,
        requests_mock,
        accept_licenses_command_factory,
        success_response_factory,
    ):
        command: AcceptLicensesCommand = accept_licenses_command_factory.build()
        mock_application = success_response_factory.build()
        requests_mock.post(
            url=f"{rems_client.base_url}/api/applications/accept-licenses",
            json=mock_application.model_dump(by_alias=True, exclude_unset=True),
        )

        application = rems_client.accept_licenses(
            command.application_id, command.accepted_licenses
        )

        assert isinstance(application, SuccessResponse)
        assert application.success == mock_application.success

    def test_submit_application(
        self,
        rems_client,
        requests_mock,
        create_application_command_factory,
        success_response_factory,
    ):
        command: CreateApplicationCommand = create_application_command_factory.build()
        mock_application = success_response_factory.build()
        requests_mock.post(
            url=f"{rems_client.base_url}/api/applications/submit",
            json=mock_application.model_dump(by_alias=True, exclude_unset=True),
        )

        application = rems_client.submit_application(command.catalogue_item_ids[0])

        assert isinstance(application, SuccessResponse)
        assert application.success == mock_application.success

    def test_add_attachment(self, rems_client, requests_mock):
        application_id = 1
        attachment_id = 123
        test_file_text = "big_text"

        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(test_file_text.encode("utf-8"))
            temp_file.seek(0)
            temp_file_path = temp_file.name

            def files_matcher(request):
                file_found, application_id_found = False, False
                if test_file_text in request.text:
                    file_found = True
                if f"application-id={application_id}" in request.query:
                    application_id_found = True
                return file_found and application_id_found

            requests_mock.register_uri(
                "POST",
                f"{rems_client.base_url}/api/applications/add-attachment",
                additional_matcher=files_matcher,
                json={"id": attachment_id},
            )
            result = rems_client.add_attachment(application_id, temp_file_path)

            assert result == attachment_id

    def test_create_resource(
        self,
        rems_client,
        requests_mock,
        create_resource_command_factory,
        create_response_factory,
    ):
        command: CreateResourceCommand = create_resource_command_factory.build()
        resp = create_response_factory.build()
        requests_mock.post(
            url=f"{rems_client.base_url}/api/resources/create",
            json=resp.model_dump(by_alias=True, exclude_unset=True),
        )

        resource = rems_client.create_resource(
            command.organization.id, command.resid, command.licenses
        )
        assert isinstance(resource, CreateResponse)
