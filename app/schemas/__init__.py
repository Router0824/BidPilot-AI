from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


# ── Auth ──
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserInfo(BaseModel):
    id: str
    username: str
    role: str
    display_name: str


class LLMConfigUpdate(BaseModel):
    provider: Literal["mock", "openai", "deepseek", "custom"] = "mock"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    fast_model: Optional[str] = None
    quality_model: Optional[str] = None
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    cost_limit_per_project: float = Field(default=0.0, ge=0)
    estimated_cost_per_1k_tokens: float = Field(default=0.0, ge=0)


# ── Project ──
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    project_type: str = "software"
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    owner_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    project_type: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    project_type: str
    owner_id: str
    owner_name: Optional[str] = None
    deadline: Optional[datetime] = None
    status: str
    workflow_status: str
    description: Optional[str] = None
    document_count: int = 0
    requirement_count: int = 0
    high_risk_count: int = 0
    pending_confirmation_count: int = 0
    outline_completion: float = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Document ──
class DocumentCreate(BaseModel):
    name: str
    document_type: str = "tender_main"
    version: str = "1"
    priority: int = 0
    supersedes_document_id: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    name: str
    document_type: str
    version: str
    file_size: Optional[int] = None
    parse_status: str
    page_count: int
    is_latest: bool
    priority: int
    uploaded_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentPageResponse(BaseModel):
    id: str
    document_id: str
    page_number: int
    text: Optional[str] = None
    parse_method: Optional[str] = None
    ocr_confidence: Optional[float] = None
    table_count: int = 0

    model_config = {"from_attributes": True}


# ── Project Fact ──
class ProjectFactResponse(BaseModel):
    id: str
    project_id: str
    fact_key: str
    fact_value: Optional[str] = None
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    confidence: Optional[float] = None
    confirmation_status: str
    confirmed_by: Optional[str] = None
    version: int
    risk_level: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectFactUpdate(BaseModel):
    fact_value: Optional[str] = None
    confirmation_status: Optional[str] = None
    risk_level: Optional[str] = None


# ── Requirement ──
class RequirementResponse(BaseModel):
    id: str
    project_id: str
    requirement_text: str
    requirement_type: str
    mandatory: bool
    risk_level: str
    evidence_required: Optional[str] = None
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    confidence: Optional[float] = None
    response_section_id: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    status: str
    review_status: Optional[str] = None
    subject: Optional[str] = None
    action: Optional[str] = None
    condition: Optional[str] = None
    deadline: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequirementUpdate(BaseModel):
    requirement_text: Optional[str] = None
    requirement_type: Optional[str] = None
    mandatory: Optional[bool] = None
    risk_level: Optional[str] = None
    evidence_required: Optional[str] = None
    response_section_id: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    status: Optional[str] = None


class RequirementMerge(BaseModel):
    source_ids: list[str]
    target_id: Optional[str] = None


# ── Scoring ──
class ScoringItemResponse(BaseModel):
    id: str
    project_id: str
    parent_id: Optional[str] = None
    title: str
    score: float
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    criteria: Optional[str] = None
    evidence: Optional[str] = None
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    coverage_status: str
    suggested_section_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Outline ──
class OutlineSectionCreate(BaseModel):
    title: str
    parent_id: Optional[str] = None
    level: int = 1
    sort_order: int = 0
    target_word_count: Optional[int] = None
    owner_id: Optional[str] = None


class OutlineSectionUpdate(BaseModel):
    title: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None
    target_word_count: Optional[int] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    status: Optional[str] = None


class OutlineSectionResponse(BaseModel):
    id: str
    project_id: str
    parent_id: Optional[str] = None
    title: str
    level: int
    sort_order: int
    target_word_count: Optional[int] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    status: str
    current_version_id: Optional[str] = None
    children: list["OutlineSectionResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Draft ──
class DraftGenerateRequest(BaseModel):
    style: Optional[str] = "formal"
    max_words: Optional[int] = 2000


class DraftVersionResponse(BaseModel):
    id: str
    section_id: str
    content: Optional[str] = None
    citations: Optional[list] = None
    generated_by: Optional[str] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    status: str
    word_count: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Workflow ──
class WorkflowRunResponse(BaseModel):
    id: str
    project_id: str
    definition_key: str
    definition_version: str
    current_node: Optional[str] = None
    status: str
    version: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int
    node_runs: list["NodeRunResponse"] = []

    model_config = {"from_attributes": True}


class NodeRunResponse(BaseModel):
    id: str
    workflow_run_id: str
    node_name: str
    agent_name: Optional[str] = None
    status: str
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    token_usage: Optional[int] = None
    latency_ms: Optional[int] = None
    retry_count: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowStartRequest(BaseModel):
    definition_key: str = "tender_mvp"
    definition_version: str = "1.0.0"
    document_ids: list[str] = []


class WorkflowImpactPreviewRequest(BaseModel):
    change_type: Literal["documents_changed", "addendum_uploaded", "manual_confirmation_changed", "reviewer_issues_changed"] = "documents_changed"
    changed_document_ids: list[str] = []


class WorkflowIncrementalRunRequest(WorkflowImpactPreviewRequest):
    preview_id: Optional[str] = None
    confirm_high_risk: bool = False


# ── Confirmation ──
class ConfirmationTaskResponse(BaseModel):
    id: str
    project_id: str
    task_type: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    candidate_value: Optional[dict] = None
    source_document_id: Optional[str] = None
    source_page: Optional[int] = None
    risk_level: Optional[str] = None
    conflicts: Optional[list] = None
    status: str
    assigned_to: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConfirmationAction(BaseModel):
    action: Literal["approve", "modify_and_approve", "reject", "mark_uncertain"]
    value: Optional[str] = None
    resource_version: int = 1
    comment: Optional[str] = None


# ── Review ──
class ReviewRunResponse(BaseModel):
    id: str
    project_id: str
    review_type: str
    status: str
    findings: Optional[list] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReviewFindingResponse(BaseModel):
    id: str
    review_run_id: str
    finding_type: Optional[str] = None
    risk_level: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    evidence: Optional[str] = None
    suggestion: Optional[str] = None
    owner_id: Optional[str] = None
    status: str
    ignore_reason: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Export ──
class ExportRequest(BaseModel):
    export_type: Literal["requirements", "risk_list", "outline", "full_document", "draft"]
    format: Literal["markdown", "docx", "xlsx"] = "markdown"


class ExportJobResponse(BaseModel):
    id: str
    project_id: str
    export_type: str
    format: str
    status: str
    file_path: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Knowledge ──
class KnowledgeChunkResponse(BaseModel):
    id: str
    material_name: Optional[str] = None
    material_type: Optional[str] = None
    product_line: Optional[str] = None
    content: Optional[str] = None
    document_version: Optional[str] = None
    source_page: Optional[int] = None
    is_audited: bool
    is_expired: bool
    access_level: str

    model_config = {"from_attributes": True}


# ── API Response Wrapper ──
class APIResponse(BaseModel):
    code: str = "SUCCESS"
    message: str = "ok"
    request_id: str = Field(default_factory=new_id)
    data: Optional[dict | list] = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str = Field(default_factory=new_id)
    details: Optional[dict] = None
