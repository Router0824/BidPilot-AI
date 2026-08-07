from enum import Enum
from typing import Callable, Awaitable
from pydantic import BaseModel
from dataclasses import dataclass, field


class WorkflowNodeStatus(str, Enum):
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


class ProjectWorkflowStatus(str, Enum):
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


@dataclass
class NodeDefinition:
    name: str
    version: str = "1.0.0"
    executor: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    invalidated_by: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    max_retries: int = 2
    retry_backoff_seconds: list[int] = field(default_factory=lambda: [5, 30])
    human_gate: bool = False
    risk_level: str = "medium"
    requires_human_confirmation: bool = False
    idempotency_key: str = ""
    next_on_success: list[str] = field(default_factory=list)
    next_on_failure: str = "manual_queue"
    allowed_models: list[str] = field(default_factory=lambda: ["mock-llm"])
    cost_limit: float = 0.0

    def __post_init__(self):
        if not self.idempotency_key:
            self.idempotency_key = f"{self.name}:{self.version}"
        self.requires_human_confirmation = self.requires_human_confirmation or self.human_gate


TENDER_WORKFLOW_DEFINITION = {
    "key": "tender_mvp",
    "version": "1.0.0",
    "nodes": [
        NodeDefinition(
            name="parse_documents",
            executor="document_agent.parse",
            inputs=["uploaded_documents"],
            outputs=["document_pages", "document_parse_results"],
            invalidated_by=["document_added", "document_updated", "document_deleted"],
            timeout_seconds=600,
            next_on_success=["extract_project_facts"],
            risk_level="low",
        ),
        NodeDefinition(
            name="extract_project_facts",
            executor="requirement_agent.extract_facts",
            inputs=["document_pages"],
            outputs=["project_facts"],
            dependencies=["parse_documents"],
            invalidated_by=["document_pages", "addendum_document", "manual_fact_confirmation"],
            human_gate=True,
            next_on_success=["detect_addendum_conflicts"],
            risk_level="high",
        ),
        NodeDefinition(
            name="detect_addendum_conflicts",
            executor="addendum_agent.detect_conflicts",
            inputs=["project_facts", "addendum_document"],
            outputs=["addendum_conflicts", "confirmation_tasks"],
            dependencies=["extract_project_facts"],
            invalidated_by=["addendum_document", "project_facts"],
            next_on_success=["extract_requirements"],
            risk_level="high",
        ),
        NodeDefinition(
            name="extract_requirements",
            executor="requirement_agent.extract_requirements",
            inputs=["document_pages", "project_facts", "addendum_conflicts"],
            outputs=["requirements"],
            dependencies=["detect_addendum_conflicts"],
            invalidated_by=["document_pages", "addendum_conflicts", "manual_fact_confirmation"],
            human_gate=True,
            next_on_success=["extract_scoring"],
            risk_level="high",
        ),
        NodeDefinition(
            name="extract_scoring",
            executor="scoring_agent.extract_scoring",
            inputs=["document_pages", "requirements"],
            outputs=["scoring_items"],
            dependencies=["extract_requirements"],
            invalidated_by=["document_pages", "requirements"],
            next_on_success=["generate_matrix"],
            risk_level="medium",
        ),
        NodeDefinition(
            name="generate_matrix",
            executor="requirement_agent.generate_matrix",
            inputs=["requirements", "scoring_items"],
            outputs=["requirement_matrix"],
            dependencies=["extract_requirements", "extract_scoring"],
            invalidated_by=["requirements", "scoring_items"],
            next_on_success=["generate_outline"],
            risk_level="medium",
        ),
        NodeDefinition(
            name="generate_outline",
            executor="drafting_agent.generate_outline",
            inputs=["requirements", "scoring_items", "project_facts"],
            outputs=["outline_sections"],
            dependencies=["generate_matrix"],
            invalidated_by=["requirements", "scoring_items", "project_facts", "manual_confirmation"],
            human_gate=True,
            next_on_success=["retrieve_knowledge"],
            risk_level="medium",
        ),
        NodeDefinition(
            name="retrieve_knowledge",
            executor="retrieval_agent.retrieve",
            inputs=["outline_sections", "requirements", "project_facts", "knowledge_chunks"],
            outputs=["retrieved_knowledge"],
            dependencies=["generate_outline"],
            invalidated_by=["outline_sections", "requirements", "knowledge_chunks"],
            next_on_success=["generate_draft"],
            risk_level="low",
        ),
        NodeDefinition(
            name="generate_draft",
            executor="drafting_agent.generate_draft",
            inputs=["outline_sections", "requirements", "project_facts", "retrieved_knowledge"],
            outputs=["draft_versions"],
            dependencies=["retrieve_knowledge"],
            invalidated_by=["outline_sections", "requirements", "project_facts", "retrieved_knowledge"],
            human_gate=True,
            next_on_success=["review_document"],
            timeout_seconds=600,
            risk_level="high",
        ),
        NodeDefinition(
            name="review_document",
            executor="review_agent.review",
            inputs=["draft_versions", "requirements", "project_facts"],
            outputs=["review_findings"],
            dependencies=["generate_draft"],
            invalidated_by=["draft_versions", "requirements", "project_facts"],
            next_on_success=["ready_to_export"],
            risk_level="medium",
        ),
        NodeDefinition(
            name="ready_to_export",
            executor="export_service.export",
            inputs=["draft_versions", "review_findings"],
            outputs=["export_readiness"],
            dependencies=["review_document"],
            invalidated_by=["draft_versions", "review_findings"],
            human_gate=False,
            next_on_success=[],
            risk_level="low",
        ),
    ],
}


STATUS_TRANSITIONS = {
    ProjectWorkflowStatus.CREATED: [ProjectWorkflowStatus.FILES_UPLOADED],
    ProjectWorkflowStatus.FILES_UPLOADED: [ProjectWorkflowStatus.PARSING],
    ProjectWorkflowStatus.PARSING: [ProjectWorkflowStatus.PARSED, ProjectWorkflowStatus.FAILED],
    ProjectWorkflowStatus.PARSED: [ProjectWorkflowStatus.EXTRACTING_REQUIREMENTS],
    ProjectWorkflowStatus.EXTRACTING_REQUIREMENTS: [ProjectWorkflowStatus.WAITING_FOR_CONFIRMATION, ProjectWorkflowStatus.FAILED],
    ProjectWorkflowStatus.WAITING_FOR_CONFIRMATION: [ProjectWorkflowStatus.FACTS_CONFIRMED, ProjectWorkflowStatus.FAILED],
    ProjectWorkflowStatus.FACTS_CONFIRMED: [ProjectWorkflowStatus.MATRIX_GENERATED],
    ProjectWorkflowStatus.MATRIX_GENERATED: [ProjectWorkflowStatus.OUTLINE_GENERATED],
    ProjectWorkflowStatus.OUTLINE_GENERATED: [ProjectWorkflowStatus.DRAFTING],
    ProjectWorkflowStatus.DRAFTING: [ProjectWorkflowStatus.DRAFT_COMPLETED, ProjectWorkflowStatus.FAILED],
    ProjectWorkflowStatus.DRAFT_COMPLETED: [ProjectWorkflowStatus.REVIEWING],
    ProjectWorkflowStatus.REVIEWING: [ProjectWorkflowStatus.REVIEW_COMPLETED, ProjectWorkflowStatus.FAILED],
    ProjectWorkflowStatus.REVIEW_COMPLETED: [ProjectWorkflowStatus.READY_TO_EXPORT],
    ProjectWorkflowStatus.READY_TO_EXPORT: [ProjectWorkflowStatus.EXPORTED],
    ProjectWorkflowStatus.FAILED: [ProjectWorkflowStatus.RETRYING, ProjectWorkflowStatus.CANCELLED],
    ProjectWorkflowStatus.RETRYING: list(ProjectWorkflowStatus),
}

NODE_TO_STATUS_MAP = {
    "parse_documents": ProjectWorkflowStatus.PARSING,
    "extract_project_facts": ProjectWorkflowStatus.EXTRACTING_REQUIREMENTS,
    "detect_addendum_conflicts": ProjectWorkflowStatus.EXTRACTING_REQUIREMENTS,
    "extract_requirements": ProjectWorkflowStatus.EXTRACTING_REQUIREMENTS,
    "extract_scoring": ProjectWorkflowStatus.EXTRACTING_REQUIREMENTS,
    "generate_matrix": ProjectWorkflowStatus.MATRIX_GENERATED,
    "generate_outline": ProjectWorkflowStatus.OUTLINE_GENERATED,
    "retrieve_knowledge": ProjectWorkflowStatus.DRAFTING,
    "generate_draft": ProjectWorkflowStatus.DRAFTING,
    "review_document": ProjectWorkflowStatus.REVIEWING,
    "ready_to_export": ProjectWorkflowStatus.READY_TO_EXPORT,
}


def get_node_definition(node_name: str) -> NodeDefinition | None:
    for node in TENDER_WORKFLOW_DEFINITION["nodes"]:
        if node.name == node_name:
            return node
    return None


def get_next_node(node_name: str, success: bool = True) -> str | None:
    node = get_node_definition(node_name)
    if not node:
        return None
    if success:
        return node.next_on_success[0] if node.next_on_success else None
    return node.next_on_failure


def get_status_for_node(node_name: str) -> ProjectWorkflowStatus:
    return NODE_TO_STATUS_MAP.get(node_name, ProjectWorkflowStatus.FAILED)
