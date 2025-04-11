from typing import List, Optional, Dict, Any, Union
import os

import mimetypes
import requests
from pydantic import BaseModel, Field


class UserWithAttributes(BaseModel):
    user_id: str = Field(..., alias="userid")
    name: str = Field(..., alias="name")
    email: str = Field(..., alias="email")


class Workflow(BaseModel):
    id: int = Field(None, alias="workflow/id")
    type: str = Field(None, alias="workflow/type")


class V2Resource(BaseModel):
    end: Optional[str] = Field(..., alias="catalogue-item/end")
    expired: bool = Field(None, alias="catalogue-item/expired")
    enabled: bool = Field(None, alias="catalogue-item/enabled")
    id: int = Field(None, alias="resource/id")
    title: Dict[str, str] = Field(..., alias="catalogue-item/title")
    infourl: Dict[str, str] = Field(..., alias="catalogue-item/infourl")
    ext_id: str = Field(None, alias="resource/ext-id")
    start: str = Field(None, alias="catalogue-item/start")
    archived: bool = Field(None, alias="catalogue-item/archived")
    catalog_item_id: int = Field(None, alias="catalogue-item/id")


class ApplicationAttachment(BaseModel):
    id: int = Field(None, alias="attachment/id")
    filename: str = Field(None, alias="attachment/filename")
    type: str = Field(None, alias="attachment/type")
    event: Dict[str, Any] = Field(None, alias="attachment/event")


class Application(BaseModel):
    workflow: Workflow = Field(None, alias="application/workflow")
    external_id: str = Field(None, alias="application/external-id")
    first_submitted: str = Field(None, alias="application/first-submitted")
    blacklist: List[Dict[str, Any]] = Field(None, alias="application/blacklist")
    id: int = Field(None, alias="application/id")
    applicant: UserWithAttributes = Field(None, alias="application/applicant")
    todo: Optional[str] = Field(None, alias="application/todo")
    members: List[UserWithAttributes] = Field(None, alias="application/members")
    end: Optional[str] = Field(None, alias="entitlement/end")
    resources: List[V2Resource] = Field(None, alias="application/resources")
    accepted_licenses: Dict[str, List[int]] = Field(
        None, alias="application/accepted-licenses"
    )
    invited_members: List[Dict[str, str]] = Field(
        None, alias="application/invited-members"
    )
    description: str = Field(None, alias="application/description")
    generated_external_id: Optional[str] = Field(
        None, alias="application/generated-external-id"
    )
    permissions: List[str] = Field(None, alias="application/permissions")
    last_activity: str = Field(None, alias="application/last-activity")
    roles: List[str] = Field(None, alias="application/roles")
    attachments: List[ApplicationAttachment] = Field(
        None, alias="application/attachments"
    )
    created: str = Field(None, alias="application/created")
    state: str = Field(None, alias="application/state")
    modified: str = Field(None, alias="application/modified")


class ApplicationDelete(BaseModel):
    application_id: int


class OrganizationOverview(BaseModel):
    id: str = Field(None, alias="organization/id")
    short_name: Dict[str, str] = Field(None, alias="organization/short-name")
    name: Dict[str, str] = Field(None, alias="organization/name")


class CatalogueItem(BaseModel):
    archived: bool
    localizations: Dict[str, Any]
    resource_id: int = Field(None, alias="resource-id")
    start: str
    resource_name: Optional[str] = Field(None, alias="resource-name")
    organization: Dict[str, Any]
    wfid: int
    resid: str
    form_id: int = Field(None, alias="formid")
    categories: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_name: Optional[str] = Field(None, alias="workflow-name")
    id: int
    expired: bool
    end: Optional[str]
    enabled: bool


class FormTemplateFieldsOptions(BaseModel):
    key: str
    label: Dict[str, str]


class FormField(BaseModel):
    fieldtitle: Dict[str, str] = Field(None, alias="field/title")
    fieldtype: str = Field(None, alias="field/type")
    fieldid: str = Field(None, alias="field/id")
    fieldoptional: bool = Field(None, alias="field/optional")
    fieldmax_length: Optional[int] = Field(None, alias="field/max-length")
    fieldplaceholder: Optional[Dict[str, str]] = Field(None, alias="field/placeholder")
    fieldoptions: Optional[List[FormTemplateFieldsOptions]] = Field(
        None, alias="field/options"
    )


class Form(BaseModel):
    archived: bool
    internal_name: str = Field(None, alias="form/internal-name")
    title: str = Field(None, alias="form/title")
    organization: OrganizationOverview
    errors: Optional[Dict[str, Any]] = Field(None, alias="form/errors")
    id: int = Field(None, alias="form/id")
    external_title: Dict[str, str] = Field(None, alias="form/external-title")
    enabled: bool
    fields: List[FormField] = Field(None, alias="form/fields")


class CreateApplicationCommand(BaseModel):
    catalogue_item_ids: List[int] = Field(..., alias="catalogue-item-ids")


class CreateApplicationResponse(BaseModel):
    success: bool
    application_id: Optional[int] = Field(None, alias="application-id")

    @classmethod
    def model_validate_json(cls, json_data):
        if isinstance(json_data, (str, bytes, bytearray)):
            return super().model_validate_json(json_data)
        return cls.model_validate(json_data)


class SaveDraftCommandFieldValues(BaseModel):
    form: int
    field: str
    value: str


class SaveDraftCommand(BaseModel):
    application_id: int = Field(..., alias="application-id")
    field_values: List[SaveDraftCommandFieldValues] = Field(..., alias="field-values")


class SuccessResponse(BaseModel):
    success: bool
    errors: Optional[List[Dict[str, Union[str, int]]]] = None


class AcceptLicensesCommand(BaseModel):
    application_id: int = Field(..., alias="application-id")
    accepted_licenses: List[int] = Field(..., alias="accepted-licenses")


class OrganizationId(BaseModel):
    id: str = Field(..., alias="organization/id")


class ResourceLicense(BaseModel):
    id: int
    licensetype: str
    organization: OrganizationOverview
    enabled: bool
    archived: bool
    localizations: Dict[str, Any]


class Resource(BaseModel):
    id: int
    organization: OrganizationOverview
    resid: str = Field(..., alias="resid")
    enabled: bool
    archived: bool
    licenses: List[ResourceLicense]
    duo: Dict[str, Any] = Field(..., alias="resource/duo")


class CreateResourceCommand(BaseModel):
    organization: OrganizationId
    resid: str
    licenses: List[int]


class EditCatalogueItemCommand(BaseModel):
    id: int
    localizations: Dict[str, Any]


class CreateCatalogueItemCommand(BaseModel):
    resid: int
    form: int
    wfid: int
    enabled: bool
    localizations: Dict[str, Any]
    organization: OrganizationId


class CreateResponse(BaseModel):
    success: bool
    id: Optional[int]


class RemsClient:
    """
    + POST api/users/create
    + GET api/applications
    + GET api/applications/{application-id}
    + POST api/applications/close
    + GET api/my-applications
    + GET api/catalogue-items/{item-id}
    + GET api/forms/{form-id}
    + POST api/applications/create
    + POST api/applications/save-draft
    + GET api/resources/{resource-id}
    + POST api/resources/create
    + POST api/applications/accept-licenses
    + POST api/applications/submit
    POST api/applications/add-attachment
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_username: str = None,
        admin_user: str = None,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.api_username = api_username
        self.auth_headers = {
            "x-rems-api-key": self.api_key,
            "x-rems-user-id": self.api_username,
        }
        # Always initialize auth_headers_admin, using admin_user if provided
        self.auth_headers_admin = {
            "x-rems-api-key": self.api_key,
            "x-rems-user-id": admin_user if admin_user else self.api_username,
        }
        self.verify_ssl = verify_ssl

    def create_user(self, user_id, name, email) -> bool:
        """POST /api/users/create"""
        url = f"{self.base_url}/api/users/create"
        command = UserWithAttributes(userid=user_id, name=name, email=email)
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers_admin,
                verify=self.verify_ssl,
                json=command.model_dump(by_alias=True, exclude_unset=True),
            )
            response.raise_for_status()
            return response.ok

    def get_my_applications(self) -> List[Application]:
        """GET /api/my-applications"""
        url = f"{self.base_url}/api/my-applications"
        with requests.Session() as session:
            response = session.get(
                url, headers=self.auth_headers, verify=self.verify_ssl
            )
            response.raise_for_status()
            applications = [Application.model_validate(app) for app in response.json()]
            return applications

    def get_applications(self, query: Optional[str] = None) -> List[Application]:
        """GET /api/applications"""
        url = f"{self.base_url}/api/applications"
        with requests.Session() as session:
            response = session.get(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                params={"query": query},
            )
            response.raise_for_status()
            applications = [Application.model_validate(app) for app in response.json()]
            return applications

    def get_application(self, application_id: int) -> Application:
        """GET /api/applications/{application-id}"""
        url = f"{self.base_url}/api/applications/{application_id}"
        with requests.Session() as session:
            response = session.get(
                url, headers=self.auth_headers, verify=self.verify_ssl
            )
            response.raise_for_status()
            application = Application.model_validate_json(response.text)
            return application

    def close_application(self, application_id: int) -> None:
        """POST /api/applications/close"""
        url = f"{self.base_url}/api/applications/close"
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers_admin,
                verify=self.verify_ssl,
                json={"application-id": application_id},
            )
            response.raise_for_status()

    def create_application(
        self, catalogue_item_ids: List[int]
    ) -> CreateApplicationResponse:
        """POST /api/applications/create"""
        url = f"{self.base_url}/api/applications/create"
        command = CreateApplicationCommand(**{"catalogue-item-ids": catalogue_item_ids})
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                json=command.model_dump(by_alias=True, exclude_unset=True),
            )
            response.raise_for_status()
            create_response = CreateApplicationResponse.model_validate_json(
                response.text
            )
            return create_response

    def save_draft(
        self, application_id: int, field_values: List[Dict[str, Any]]
    ) -> SuccessResponse:
        """POST /api/applications/save-draft"""
        url = f"{self.base_url}/api/applications/save-draft"
        command = SaveDraftCommand(
            **{"application-id": application_id, "field-values": field_values}
        )
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                json=command.model_dump(by_alias=True, exclude_unset=True),
            )
            response.raise_for_status()
            save_response = SuccessResponse.model_validate_json(response.text)
            return save_response

    def accept_licenses(
        self, application_id: int, accepted_licenses: List[int]
    ) -> SuccessResponse:
        """POST /api/applications/accept-licenses"""
        url = f"{self.base_url}/api/applications/accept-licenses"
        command = AcceptLicensesCommand(
            **{"application-id": application_id, "accepted-licenses": accepted_licenses}
        )
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                json=command.model_dump(by_alias=True, exclude_unset=True),
            )
            response.raise_for_status()
            accept_response = SuccessResponse.model_validate_json(response.text)
            return accept_response

    def submit_application(self, application_id: int) -> SuccessResponse:
        """POST /api/applications/submit"""
        url = f"{self.base_url}/api/applications/submit"
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                json={"application-id": application_id},
            )
            response.raise_for_status()
            submit_response = SuccessResponse.model_validate_json(response.text)
            return submit_response

    def get_catalogue_item(self, item_id: int) -> CatalogueItem:
        """GET /api/catalogue-items/{item-id}"""
        url = f"{self.base_url}/api/catalogue-items/{item_id}"
        with requests.Session() as session:
            response = session.get(
                url, headers=self.auth_headers, verify=self.verify_ssl
            )
            response.raise_for_status()
            catalogue_item = CatalogueItem.model_validate_json(response.text)
            return catalogue_item

    def get_catalogue_items(self, resource: str) -> List[CatalogueItem]:
        """GET /api/catalogue-items"""
        url = f"{self.base_url}/api/catalogue-items"
        with requests.Session() as session:
            response = session.get(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                params={"resource": resource},
            )
            response.raise_for_status()
            catalog_items = [
                CatalogueItem.model_validate(res) for res in response.json()
            ]
            return catalog_items

    def edit_catalogue_items(self, id: int, localizations: Any) -> CatalogueItem:
        """PUT /api/catalogue-items"""
        url = f"{self.base_url}/api/catalogue-items/edit"

        command = EditCatalogueItemCommand(id=id, localizations=localizations)
        with requests.Session() as session:
            response = session.put(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                json=command.model_dump(by_alias=True, exclude_unset=True),
            )
            response.raise_for_status()
            catalogue_item = SuccessResponse.model_validate_json(response.text)
            return catalogue_item

    def create_catalogue_items(
        self,
        res_id_int: int,
        form_id: int,
        wfid: int,
        localizations: Any,
        organization_id: str,
    ) -> CatalogueItem:
        """POST /api/catalogue-items"""
        url = f"{self.base_url}/api/catalogue-items/create"
        organization = OrganizationId(**{"organization/id": organization_id})

        command = CreateCatalogueItemCommand(
            resid=res_id_int,
            form=form_id,
            wfid=wfid,
            enabled=True,
            localizations=localizations,
            organization=organization,
        )
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                json=command.model_dump(by_alias=True, exclude_unset=True),
            )
            response.raise_for_status()
            create_response = CreateResponse.model_validate_json(response.text)
            return create_response

    def get_form(self, form_id: int) -> Form:
        """GET /api/forms/{form-id}"""
        url = f"{self.base_url}/api/forms/{form_id}"
        with requests.Session() as session:
            response = session.get(
                url, headers=self.auth_headers_admin, verify=self.verify_ssl
            )
            response.raise_for_status()
            form = Form.model_validate_json(response.text)
            return form

    def get_resources(self) -> List[Resource]:
        """GET /api/resources/"""
        url = f"{self.base_url}/api/resources"
        with requests.Session() as session:
            response = session.get(
                url, headers=self.auth_headers_admin, verify=self.verify_ssl
            )
            response.raise_for_status()
            resources = [Resource.model_validate(res) for res in response.json()]
            return resources

    def get_resource(self, resource_id: int) -> Resource:
        """GET /api/resources/{resource-id}"""
        url = f"{self.base_url}/api/resources/{resource_id}"
        with requests.Session() as session:
            response = session.get(
                url, headers=self.auth_headers_admin, verify=self.verify_ssl
            )
            response.raise_for_status()
            resource = Resource.model_validate_json(response.text)
            return resource

    def create_resource(
        self, organization_id: str, resid: str, license_ids: List[int]
    ) -> Resource:
        """POST /api/resources/create"""
        url = f"{self.base_url}/api/resources/create"
        organization = OrganizationId(**{"organization/id": organization_id})
        command = CreateResourceCommand(
            organization=organization, resid=resid, licenses=license_ids
        )
        with requests.Session() as session:
            response = session.post(
                url,
                headers=self.auth_headers,
                verify=self.verify_ssl,
                json=command.model_dump(by_alias=True, exclude_unset=True),
            )
            response.raise_for_status()
            create_response = CreateResponse.model_validate_json(response.text)
            return create_response

    def add_attachment(self, application_id: int, file_path: str) -> int:
        """POST /api/applications/add-attachment"""
        url = f"{self.base_url}/api/applications/add-attachment"

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as file:
            content_type = (
                mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            )
            files = {"file": (os.path.basename(file_path), file, content_type)}

            with requests.Session() as session:
                response = session.post(
                    url,
                    headers=self.auth_headers,
                    verify=self.verify_ssl,
                    files=files,
                    params={"application-id": application_id},
                )
                response.raise_for_status()
                return response.json()["id"]


"""
EXAMPLE

app = FastAPI()

REMS_API_KEY = os.environ.get("REMS_API_KEY")
REMS_URL = os.environ.get("REMS_URL", "http://epnd-connector-srv.lcsb.uni.lu:8080")
REMS_API_USER = os.environ.get("REMS_API_USER", "admin")

rems_client = RemsClient(
    base_url=REMS_URL,
    api_key=REMS_API_KEY,
    api_username=REMS_API_USER,
    admin_user=REMS_API_USER,
)

@app.post("/users/create")
def create_user(user: UserWithAttributes):
    try:
        return rems_client.create_user(user.user_id, user.name, user.email)
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.get("/applications", response_model=List[Application])
def get_applications():
    try:
        return rems_client.get_applications()
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@app.post("/applications/add-attachment/{application_id}")
def add_attachment(application_id: int, file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(file.file.read())
        temp_file.seek(0)
        temp_file_path = temp_file.name
    try:
        return rems_client.add_attachment(application_id, temp_file_path)
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    finally:
        os.unlink(temp_file_path)
"""
