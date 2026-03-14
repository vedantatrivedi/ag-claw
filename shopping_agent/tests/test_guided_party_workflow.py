from __future__ import annotations

from unittest import mock

from shopping_agent.app.models import AgentResponse
from shopping_agent.app.workflows.guided_party_workflow import GuidedPartyWorkflow


REQUEST = "It's my son's birthday tomorrow, I want to plan a themed party"
QUESTIONS = [
    "What theme or characters does he like?",
    "Anything he dislikes or should we avoid?",
    "What is his favorite color?",
    "How many guests are expected?",
]
ANSWERS = {
    "What theme or characters does he like?": "Spider-Man",
    "Anything he dislikes or should we avoid?": "No scary themes",
    "What is his favorite color?": "Blue",
    "How many guests are expected?": "12",
}


class StubQuestionAgent:
    def __init__(self, questions: list[str]):
        self.questions = questions

    def generate_questions(self, user_request: str) -> AgentResponse:
        assert user_request == REQUEST
        return AgentResponse(success=True, data={"questions": self.questions})


class StubPlanner:
    def __init__(self, response: AgentResponse):
        self.response = response

    def plan(self, user_request: str, apply_postprocessing: bool = True) -> AgentResponse:
        assert "Spider-Man" in user_request
        assert "Budget: INR 15000.00" in user_request
        assert apply_postprocessing is True
        return self.response


def _planner_success_response() -> AgentResponse:
    return AgentResponse(
        success=True,
        data={
            "plan": {
                "items": [
                    {
                        "description": "Spider-Man themed birthday banner",
                        "quantity": 1,
                        "intent": "Main party decoration for the chosen theme",
                        "required": True,
                        "search_hints": ["Spider-Man", "banner", "birthday"],
                        "constraints": ["color: blue"],
                        "search_query": "spider man birthday banner blue",
                        "preferred_sites": ["amazon", "flipkart"],
                    },
                    {
                        "description": "Spider-Man party plates and napkins set",
                        "quantity": 1,
                        "intent": "Serve 12 guests with matching tableware",
                        "required": True,
                        "search_hints": ["Spider-Man", "plates", "napkins"],
                        "constraints": ["serves 12 guests"],
                        "search_query": "spider man plates napkins set 12",
                        "preferred_sites": ["amazon", "flipkart"],
                    },
                ],
                "assumptions": ["Indoor party", "Children aged around 10"],
                "clarifications_needed": [],
            }
        },
        metadata={"model": "test-model", "tokens_used": 42, "postprocessing_applied": True},
    )


def test_guided_party_workflow_runs_full_flow_without_browser_search() -> None:
    workflow = GuidedPartyWorkflow(
        planner=StubPlanner(_planner_success_response()),
        question_agent=StubQuestionAgent(QUESTIONS),
    )

    with mock.patch(
        "shopping_agent.app.workflows.guided_party_workflow.create_budget_preauth",
        return_value={
            "success": True,
            "order_id": "ord_123",
            "status": "CREATED",
            "redirect_url": "https://checkout.example.com/ord_123",
            "budget_paisa": 1500000,
        },
    ) as create_preauth_mock, mock.patch(
        "shopping_agent.app.workflows.guided_party_workflow.get_preauth_status",
        return_value={
            "success": True,
            "order_id": "ord_123",
            "status": "AUTHORIZED",
        },
    ) as get_status_mock, mock.patch(
        "shopping_agent.app.tools.pinelabs.capture_preauth"
    ) as capture_mock, mock.patch(
        "shopping_agent.app.agents.browser_search.BrowserSearchAgent.search_multiple"
    ) as search_mock:
        questions = workflow.generate_preference_questions(REQUEST)
        preauth_result = workflow.create_preauth(
            preferences_answers=ANSWERS,
            budget_inr=15000.0,
        )
        result = workflow.complete_after_authorization(
            user_request=REQUEST,
            preferences_answers=ANSWERS,
            budget_inr=15000.0,
            preauth=preauth_result["preauth"],
        )

    assert questions == QUESTIONS
    assert preauth_result["success"] is True
    assert preauth_result["preauth"]["redirect_url"] == "https://checkout.example.com/ord_123"
    assert result["success"] is True
    assert result["preferences_answers"] == ANSWERS
    assert result["budget_inr"] == 15000.0
    assert result["preauth"]["order_id"] == "ord_123"
    assert result["preauth"]["authorized_status"] == "AUTHORIZED"
    assert len(result["plan"]["items"]) == 2
    assert len(result["listing_results"]) == 2
    assert result["listing_results"][0]["results"][0]["source"] == "placeholder"
    assert result["listing_results"][0]["results"][0]["title"] == (
        "Placeholder match for Spider-Man themed birthday banner"
    )
    assert (
        result["listing_results"][0]["results"][0]["url"]
        == "https://placeholder.local/products/spider-man-themed-birthday-banner"
    )
    create_preauth_mock.assert_called_once_with(budget_paisa=1500000)
    get_status_mock.assert_called_once_with("ord_123", wait_for_status="AUTHORIZED")
    capture_mock.assert_not_called()
    search_mock.assert_not_called()


def test_guided_party_workflow_returns_preauth_failure_without_planning() -> None:
    planner = StubPlanner(_planner_success_response())
    workflow = GuidedPartyWorkflow(
        planner=planner,
        question_agent=StubQuestionAgent(QUESTIONS),
    )

    with mock.patch(
        "shopping_agent.app.workflows.guided_party_workflow.create_budget_preauth",
        side_effect=RuntimeError("authorization timed out"),
    ), mock.patch.object(planner, "plan") as planner_mock:
        result = workflow.create_preauth(
            preferences_answers=ANSWERS,
            budget_inr=15000.0,
        )

    assert result["success"] is False
    assert result["stage"] == "preauth"
    assert "authorization timed out" in result["error"]
    planner_mock.assert_not_called()


def test_guided_party_workflow_returns_authorization_failure_without_planning() -> None:
    planner = StubPlanner(_planner_success_response())
    workflow = GuidedPartyWorkflow(
        planner=planner,
        question_agent=StubQuestionAgent(QUESTIONS),
    )

    with mock.patch(
        "shopping_agent.app.workflows.guided_party_workflow.get_preauth_status",
        side_effect=RuntimeError("preauth not authorized"),
    ), mock.patch.object(planner, "plan") as planner_mock:
        result = workflow.complete_after_authorization(
            user_request=REQUEST,
            preferences_answers=ANSWERS,
            budget_inr=15000.0,
            preauth={
                "success": True,
                "order_id": "ord_123",
                "status": "CREATED",
                "redirect_url": "https://checkout.example.com/ord_123",
                "budget_paisa": 1500000,
            },
        )

    assert result["success"] is False
    assert result["stage"] == "authorization"
    assert "preauth not authorized" in result["error"]
    planner_mock.assert_not_called()


def test_guided_party_questions_fall_back_to_default_when_agent_returns_none() -> None:
    workflow = GuidedPartyWorkflow(
        planner=StubPlanner(_planner_success_response()),
        question_agent=StubQuestionAgent([]),
    )

    questions = workflow.generate_preference_questions(REQUEST)

    assert questions == [
        "What theme or characters does he like?",
        "Anything he dislikes or should we avoid?",
        "What is his favorite color?",
        "How many guests are expected?",
    ]
