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
    timeout_seconds: int = 300
    max_retries: int = 2
    retry_backoff_seconds: list[int] = field(default_factory=lambda: [5, 30])
    human_gate: bool = False
    next_on_success: list[str] = field(default_factory=list)
    next_on_failure: str = "manual_queue"
    allowed_models: list[str] = field(default_factory=lambda: ["mock-llm"])
    cost_limit: float = 0.0


TENDER_WORKFLOW_DEFINITION = {
    "key": "tender_mvp",
    "version": "1.0.0",
    "nodes": [
        NodeDefinition(
            name="parse_documents",
            executor="document_agent.parse",
            timeout_seconds=600,
            next_on_success=["extract_project_facts"],
        ),
        NodeDefinition(
            name="extract_project_facts",
            executor="requirement_agent.extract_facts",
            human_gate=True,
            next_on_success=["detect_addendum_conflicts"],
        ),
        NodeDefinition(
            name="detect_addendum_conflicts",
            executor="addendum_agent.detect_conflicts",
            next_on_success=["extract_requirements"],
        ),
        NodeDefinition(
            name="extract_requirements",
            executor="requirement_agent.extract_requirements",
            human_gate=True,
            next_on_success=["extract_scoring"],
        ),
        NodeDefinition(
            name="extract_scoring",
            executor="scoring_agent.extract_scoring",
            next_on_success=["generate_matrix"],
        ),
        NodeDefinition(
            name="generate_matrix",
            executor="requirement_agent.generate_matrix",
            next_on_success=["generate_outline"],
        ),
        NodeDefinition(
            name="generate_outline",
            executor="drafting_agent.generate_outline",
            human_gate=True,
            next_on_success=["retrieve_knowledge"],
        ),
        NodeDefinition(
            name="retrieve_knowledge",
            executor="retrieval_agent.retrieve",
            next_on_success=["generate_draft"],
        ),
        NodeDefinition(
            name="generate_draft",
            executor="drafting_agent.generate_draft",
            human_gate=True,
            next_on_success=["review_document"],
            timeout_seconds=600,
        ),
        NodeDefinition(
            name="review_document",
            executor="review_agent.review",
            next_on_success=["ready_to_export"],
        ),
        NodeDefinition(
            name="ready_to_export",
            executor="export_service.export",
            human_gate=False,
            next_on_success=[],
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
