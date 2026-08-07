import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class WorkflowStatus(str, enum.Enum):
    CREATED = "created"
    FILES_UPLOADED = "files_uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    EXTRACTING_REQUIREMENTS = "extracting_requirements"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    FACTS_CONFIRMED = "facts_confirmed"
    MATRIX_GENERATED = "matrix_generated"
    OUTLINE_GENERATED = "outline_generated"
    DRAFTING = "drafting"
    DRAFT_COMPLETED = "draft_completed"
    REVIEWING = "reviewing"
    REVIEW_COMPLETED = "review_completed"
    READY_TO_EXPORT = "ready_to_export"
    EXPORTED = "exported"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class DocumentType(str, enum.Enum):
    TENDER_MAIN = "tender_main"
    TECHNICAL_SPEC = "technical_spec"
    SCORING_TABLE = "scoring_table"
    ADDENDUM = "addendum"
    CLARIFICATION = "clarification"
    COMPANY_PRODUCT = "company_product"
    HISTORICAL_BID = "historical_bid"
    QUALIFICATION = "qualification"
    CASE_STUDY = "case_study"


class ParseStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"
    OCR_PENDING = "ocr_pending"


class RequirementType(str, enum.Enum):
    QUALIFICATION = "qualification"
    TECHNICAL = "technical"
    COMMERCIAL = "commercial"
    SCORING = "scoring"
    DELIVERY = "delivery"
    FORMAT = "format"


class RiskLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfirmStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    MODIFIED = "modified"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class RequirementStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RESPONDED = "responded"
    MISSING = "missing"


class NodeStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    VALIDATING = "validating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    WAITING_CONFIRMATION = "waiting_confirmation"
    RETRY_SCHEDULED = "retry_scheduled"
    MANUAL_REQUIRED = "manual_required"
    CANCELLED = "cancelled"


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String(255), nullable=False)
    project_type = Column(String(100), nullable=False, default="software")
    owner_id = Column(String, nullable=False)
    owner_name = Column(String(100))
    deadline = Column(DateTime)
    status = Column(String(20), default=ProjectStatus.ACTIVE.value)
    workflow_status = Column(String(40), default=WorkflowStatus.CREATED.value)
    description = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    facts = relationship("ProjectFact", back_populates="project", cascade="all, delete-orphan")
    requirements = relationship("Requirement", back_populates="project", cascade="all, delete-orphan")
    scoring_items = relationship("ScoringItem", back_populates="project", cascade="all, delete-orphan")
    outline_sections = relationship("OutlineSection", back_populates="project", cascade="all, delete-orphan")
    workflow_runs = relationship("WorkflowRun", back_populates="project", cascade="all, delete-orphan")
    confirmation_tasks = relationship("ConfirmationTask", back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False, default=DocumentType.TENDER_MAIN.value)
    version = Column(String(20), default="1")
    file_path = Column(String(500))
    file_size = Column(Integer)
    file_hash = Column(String(64))
    parse_status = Column(String(20), default=ParseStatus.PENDING.value)
    page_count = Column(Integer, default=0)
    is_latest = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    uploaded_by = Column(String)
    effective_date = Column(DateTime)
    supersedes_document_id = Column(String)
    parse_result = Column(JSON)
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String, primary_key=True, default=new_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text)
    parse_method = Column(String(20))
    ocr_confidence = Column(Float)
    table_count = Column(Integer, default=0)
    quality_score = Column(Float)
    bounding_boxes = Column(JSON)

    document = relationship("Document", back_populates="pages")


class ProjectFact(Base):
    __tablename__ = "project_facts"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    fact_key = Column(String(100), nullable=False)
    fact_value = Column(Text)
    source_document_id = Column(String)
    source_page = Column(Integer)
    confidence = Column(Float)
    confirmation_status = Column(String(20), default=ConfirmStatus.PENDING.value)
    confirmed_by = Column(String)
    version = Column(Integer, default=1)
    risk_level = Column(String(20), default=RiskLevel.MEDIUM.value)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="facts")


class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    requirement_text = Column(Text, nullable=False)
    requirement_type = Column(String(30), nullable=False)
    mandatory = Column(Boolean, default=False)
    risk_level = Column(String(20), default=RiskLevel.MEDIUM.value)
    evidence_required = Column(Text)
    source_document_id = Column(String)
    source_page = Column(Integer)
    confidence = Column(Float)
    response_section_id = Column(String)
    owner_id = Column(String)
    owner_name = Column(String(100))
    status = Column(String(20), default=RequirementStatus.PENDING.value)
    review_status = Column(String(20))
    subject = Column(String(200))
    action = Column(String(200))
    condition = Column(Text)
    deadline = Column(String(100))
    penalty = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="requirements")


class ScoringItem(Base):
    __tablename__ = "scoring_items"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    parent_id = Column(String)
    title = Column(String(255), nullable=False)
    score = Column(Float, default=0)
    min_score = Column(Float)
    max_score = Column(Float)
    criteria = Column(Text)
    evidence = Column(Text)
    source_document_id = Column(String)
    source_page = Column(Integer)
    coverage_status = Column(String(20), default="uncovered")
    suggested_section_id = Column(String)
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="scoring_items")


class OutlineSection(Base):
    __tablename__ = "outline_sections"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    parent_id = Column(String)
    title = Column(String(255), nullable=False)
    level = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
    target_word_count = Column(Integer)
    owner_id = Column(String)
    owner_name = Column(String(100))
    status = Column(String(20), default="pending")
    current_version_id = Column(String)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="outline_sections")
    draft_versions = relationship("DraftVersion", back_populates="section", cascade="all, delete-orphan")


class DraftVersion(Base):
    __tablename__ = "draft_versions"

    id = Column(String, primary_key=True, default=new_id)
    section_id = Column(String, ForeignKey("outline_sections.id"), nullable=False)
    content = Column(Text)
    citations = Column(JSON)
    generated_by = Column(String)
    model_name = Column(String)
    prompt_version = Column(String)
    status = Column(String(20), default="draft")
    word_count = Column(Integer)
    created_at = Column(DateTime, default=utcnow)

    section = relationship("OutlineSection", back_populates="draft_versions")


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String, nullable=False)
    user_name = Column(String(100))
    role = Column(String(50), default="writer")
    access_level = Column(String(30), default="write")
    created_at = Column(DateTime, default=utcnow)


class SectionLock(Base):
    __tablename__ = "section_locks"

    id = Column(String, primary_key=True, default=new_id)
    section_id = Column(String, ForeignKey("outline_sections.id"), nullable=False)
    project_id = Column(String, nullable=False)
    locked_by = Column(String, nullable=False)
    locked_by_name = Column(String(100))
    client_id = Column(String(100))
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)


class SectionApproval(Base):
    __tablename__ = "section_approvals"

    id = Column(String, primary_key=True, default=new_id)
    section_id = Column(String, ForeignKey("outline_sections.id"), nullable=False)
    project_id = Column(String, nullable=False)
    draft_version_id = Column(String)
    submitted_by = Column(String)
    reviewer_id = Column(String)
    reviewer_name = Column(String(100))
    status = Column(String(30), default="pending")
    comment = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    definition_key = Column(String, default="tender_mvp")
    definition_version = Column(String, default="1.0.0")
    current_node = Column(String)
    status = Column(String(20), default=NodeStatus.PENDING.value)
    version = Column(Integer, default=1)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="workflow_runs")
    node_runs = relationship("NodeRun", back_populates="workflow_run", cascade="all, delete-orphan")


class NodeRun(Base):
    __tablename__ = "node_runs"

    id = Column(String, primary_key=True, default=new_id)
    workflow_run_id = Column(String, ForeignKey("workflow_runs.id"), nullable=False)
    node_name = Column(String(100), nullable=False)
    agent_name = Column(String(100))
    input_snapshot = Column(JSON)
    output_snapshot = Column(JSON)
    status = Column(String(30), default=NodeStatus.PENDING.value)
    model_name = Column(String(100))
    prompt_version = Column(String(50))
    token_usage = Column(Integer)
    latency_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    error_code = Column(String(50))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)

    workflow_run = relationship("WorkflowRun", back_populates="node_runs")


class ConfirmationTask(Base):
    __tablename__ = "confirmation_tasks"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    task_type = Column(String(50), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String)
    candidate_value = Column(JSON)
    source_document_id = Column(String)
    source_page = Column(Integer)
    risk_level = Column(String(20))
    conflicts = Column(JSON)
    created_node = Column(String(50))
    status = Column(String(20), default="pending")
    assigned_to = Column(String)
    resolved_by = Column(String)
    resolved_value = Column(JSON)
    resolution = Column(String(20))
    comment = Column(Text)
    resource_version = Column(Integer, default=1)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime)

    project = relationship("Project", back_populates="confirmation_tasks")


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    review_type = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")
    findings = Column(JSON)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime)


class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id = Column(String, primary_key=True, default=new_id)
    review_run_id = Column(String, ForeignKey("review_runs.id"), nullable=False)
    finding_type = Column(String(50))
    risk_level = Column(String(20))
    description = Column(Text)
    location = Column(String(200))
    evidence = Column(Text)
    suggestion = Column(Text)
    owner_id = Column(String)
    status = Column(String(20), default="open")
    ignore_reason = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String, primary_key=True, default=new_id)
    material_name = Column(String(255))
    material_type = Column(String(50))
    product_line = Column(String(100))
    content = Column(Text)
    document_version = Column(String(20))
    source_page = Column(Integer)
    title_path = Column(String(500))
    is_audited = Column(Boolean, default=False)
    is_expired = Column(Boolean, default=False)
    valid_until = Column(DateTime)
    access_level = Column(String(20), default="internal")
    embedding = Column(JSON)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    export_type = Column(String(30), nullable=False)
    format = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")
    file_path = Column(String(500))
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=new_id)
    tenant_id = Column(String, default="default")
    resource_type = Column(String(50))
    resource_id = Column(String)
    action = Column(String(50))
    operator = Column(String(100))
    operator_ip = Column(String(50))
    before_value = Column(JSON)
    after_value = Column(JSON)
    reason = Column(Text)
    created_at = Column(DateTime, default=utcnow)


class ConsultationSession(Base):
    __tablename__ = "consultation_sessions"

    id = Column(String, primary_key=True, default=new_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), default="新咨询")
    created_by = Column(String)
    created_by_name = Column(String(100))
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ConsultationMessage(Base):
    __tablename__ = "consultation_messages"

    id = Column(String, primary_key=True, default=new_id)
    session_id = Column(String, ForeignKey("consultation_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text)
    citations = Column(JSON)
    meta = Column(JSON)
    created_at = Column(DateTime, default=utcnow)


class OpportunityMonitor(Base):
    __tablename__ = "opportunity_monitors"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String(255), nullable=False)
    source_url = Column(String(1000))
    keywords = Column(JSON)
    regions = Column(JSON)
    industry = Column(String(100))
    enabled = Column(Boolean, default=True)
    interval_minutes = Column(Integer, default=1440)
    last_run_at = Column(DateTime)
    created_by = Column(String)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True, default=new_id)
    monitor_id = Column(String, ForeignKey("opportunity_monitors.id"))
    title = Column(String(500), nullable=False)
    url = Column(String(1000))
    source = Column(String(255))
    region = Column(String(100))
    industry = Column(String(100))
    publish_date = Column(String(100))
    summary = Column(Text)
    matched_keywords = Column(JSON)
    value_score = Column(Float, default=0)
    competition_score = Column(Float, default=0)
    heat_score = Column(Float, default=0)
    ai_analysis = Column(JSON)
    status = Column(String(30), default="new")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
