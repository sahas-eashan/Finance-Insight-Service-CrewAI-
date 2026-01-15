import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerpApiGoogleSearchTool, SerperDevTool

from finance_insight_service.tools.fundamentals_fetch import FundamentalsFetchTool
from finance_insight_service.tools.market_data_fetch import MarketDataFetchTool
from finance_insight_service.tools.safe_python_exec import SafePythonExecTool


@CrewBase
class FinanceInsightCrew:
    """Research + quant crew for finance insight service."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        search_tool = _build_search_tool()
        return Agent(
            config=self.agents_config["researcher"],
            tools=[search_tool, ScrapeWebsiteTool()],
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def quant(self) -> Agent:
        return Agent(
            config=self.agents_config["quant"],
            tools=[MarketDataFetchTool(), FundamentalsFetchTool(), SafePythonExecTool()],
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def planner(self) -> Agent:
        return Agent(
            config=self.agents_config["planner"],
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def auditor(self) -> Agent:
        return Agent(
            config=self.agents_config["auditor"],
            verbose=True,
            allow_delegation=False,
        )

    @task
    def research_news_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_news_task"],
            agent=self.researcher(),
            name="research_news_task",
        )

    @task
    def quant_snapshot_task(self) -> Task:
        return Task(
            config=self.tasks_config["quant_snapshot_task"],
            agent=self.quant(),
            name="quant_snapshot_task",
        )

    @task
    def planner_task(self) -> Task:
        return Task(
            config=self.tasks_config["planner_task"],
            agent=self.planner(),
            name="planner_task",
        )

    @task
    def audit_task(self) -> Task:
        return Task(
            config=self.tasks_config["audit_task"],
            agent=self.auditor(),
            name="audit_task",
        )

    @task
    def audit_research_task(self) -> Task:
        return Task(
            config=self.tasks_config["audit_research_task"],
            agent=self.auditor(),
            name="audit_research_task",
        )

    @task
    def audit_quant_task(self) -> Task:
        return Task(
            config=self.tasks_config["audit_quant_task"],
            agent=self.auditor(),
            name="audit_quant_task",
        )

    @task
    def audit_final_task(self) -> Task:
        return Task(
            config=self.tasks_config["audit_final_task"],
            agent=self.auditor(),
            name="audit_final_task",
        )

    @task
    def final_draft_task(self) -> Task:
        return Task(
            config=self.tasks_config["final_draft_task"],
            agent=self.planner(),
            name="final_draft_task",
        )

    @task
    def final_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["final_report_task"],
            agent=self.planner(),
            name="final_report_task",
        )

    def build_crew(
        self, task_names: list[str] | None = None, include_all_agents: bool = True
    ) -> Crew:
        planner_task = self.planner_task()
        research_task = self.research_news_task()
        quant_task = self.quant_snapshot_task()
        audit_research_task = self.audit_research_task()
        audit_quant_task = self.audit_quant_task()
        final_draft_task = self.final_draft_task()
        audit_final_task = self.audit_final_task()
        final_task = self.final_report_task()

        full_order = [
            planner_task,
            research_task,
            audit_research_task,
            quant_task,
            audit_quant_task,
            final_draft_task,
            audit_final_task,
            final_task,
        ]

        task_map = {
            "planner": planner_task,
            "research": research_task,
            "quant": quant_task,
            "audit_research": audit_research_task,
            "audit_quant": audit_quant_task,
            "audit": audit_final_task,
            "final_draft": final_draft_task,
            "final_report": final_task,
        }
        if task_names:
            unknown = [name for name in task_names if name not in task_map]
            if unknown:
                raise ValueError(f"Unknown task names: {', '.join(unknown)}")
            selected_tasks = [task_map[name] for name in task_names]
        else:
            selected_tasks = full_order

        if set(selected_tasks) == set(full_order):
            research_task.context = [planner_task]
            audit_research_task.context = [planner_task, research_task]
            quant_task.context = [planner_task, research_task, audit_research_task]
            audit_quant_task.context = [
                planner_task,
                research_task,
                audit_research_task,
                quant_task,
            ]
            final_draft_task.context = [
                planner_task,
                research_task,
                audit_research_task,
                quant_task,
                audit_quant_task,
            ]
            audit_final_task.context = [
                planner_task,
                research_task,
                audit_research_task,
                quant_task,
                audit_quant_task,
                final_draft_task,
            ]
            final_task.context = [
                planner_task,
                research_task,
                audit_research_task,
                quant_task,
                audit_quant_task,
                final_draft_task,
                audit_final_task,
            ]

        if include_all_agents:
            agents = [
                self.planner(),
                self.researcher(),
                self.quant(),
                self.auditor(),
            ]
        else:
            selected_names = set(task_names or task_map.keys())
            agents = []
            if "planner" in selected_names:
                agents.append(self.planner())
            if "research" in selected_names:
                agents.append(self.researcher())
            if "quant" in selected_names:
                agents.append(self.quant())
            if "audit_research" in selected_names or "audit" in selected_names:
                agents.append(self.auditor())
            if "final_report" in selected_names and self.planner() not in agents:
                agents.append(self.planner())

        crew_name = "finance_insight_crew"

        return Crew(
            name=crew_name,
            agents=agents,
            tasks=selected_tasks,
            process=Process.sequential,
            verbose=True,
            tracing=True,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Finance Insight crew."""
        return self.build_crew()


def _build_search_tool():
    if os.getenv("SERPAPI_API_KEY"):
        return SerpApiGoogleSearchTool()
    if os.getenv("SERPER_API_KEY"):
        return SerperDevTool(search_type="news", n_results=10)
    raise ValueError("Set SERPER_API_KEY or SERPAPI_API_KEY to enable news search.")
