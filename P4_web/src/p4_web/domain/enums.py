from enum import StrEnum


class ProjectLifecycle(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class VersionStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class JobKind(StrEnum):
    GENERATE_PDF = "generate_pdf"
    GENERATE_HTML = "generate_html"
    TEXML_PDF = "texml_pdf"
    XSL_FO = "xsl_fo"
    CUT_SOURCE = "cut_source"
    EXPORT_TRANSLATION = "export_translation"
    IMPORT_TRANSLATION = "import_translation"
    PACK_MODULES = "pack_modules"
    UNPACK_MODULES = "unpack_modules"
    GENERATE_LISTS = "generate_lists"
    CHECK_INDEX = "check_index"
    CONVERT_SAP_TO_BIT_XML = "convert_sap_to_bit_xml"
    CONVERT_OPMANUAL_TO_BIT_XML = "convert_opmanual_to_bit_xml"
    ADVANCE_DELIVERY_STATUS = "advance_delivery_status"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELED = "canceled"


class ArtifactKind(StrEnum):
    PDF = "pdf"
    HTML = "html"
    XML = "xml"
    LOG = "log"
    PACKAGE = "package"
    REPORT = "report"
    OTHER = "other"


class FileRole(StrEnum):
    PROJECT_SHEET = "project_sheet"
    SOURCE_XML = "source_xml"
    KEYSEQ = "keyseq"
    LANGUAGE_SELECTION = "language_selection"
    CONFIG = "config"
    IMAGE = "image"
    STYLESHEET = "stylesheet"
    OTHER = "other"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResourcePackageKind(StrEnum):
    STYLESHEET = "stylesheet"
    IMAGE_SET = "image_set"
    GLOBAL_CONFIG = "global_config"
    TEMPLATE = "template"
