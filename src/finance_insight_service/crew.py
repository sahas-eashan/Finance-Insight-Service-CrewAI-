import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerpApiGoogleSearchTool, SerperDevTool

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
            tools=[MarketDataFetchTool(), SafePythonExecTool()],
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
        )

    @task
    def quant_snapshot_task(self) -> Task:
        return Task(
            config=self.tasks_config["quant_snapshot_task"],
            agent=self.quant(),
        )

    @task
    def planner_task(self) -> Task:
        return Task(
            config=self.tasks_config["planner_task"],
            agent=self.planner(),
        )

    @task
    def audit_task(self) -> Task:
        return Task(
            config=self.tasks_config["audit_task"],
            agent=self.auditor(),
        )

    def build_crew(self, task_names: list[str] | None = None) -> Crew:
        task_map = {
            "planner": self.planner_task(),
            "research": self.research_news_task(),
            "quant": self.quant_snapshot_task(),
            "audit": self.audit_task(),
        }
        if task_names:
            unknown = [name for name in task_names if name not in task_map]
            if unknown:
                raise ValueError(f"Unknown task names: {', '.join(unknown)}")
            selected_tasks = [task_map[name] for name in task_names]
        else:
            selected_tasks = list(task_map.values())

        selected_names = set(task_names or task_map.keys())
        agents = []
        if "planner" in selected_names:
            agents.append(self.planner())
        if "research" in selected_names:
            agents.append(self.researcher())
        if "quant" in selected_names:
            agents.append(self.quant())
        if "audit" in selected_names:
            agents.append(self.auditor())

        return Crew(
            agents=agents,
            tasks=selected_tasks,
            process=Process.sequential,
            verbose=True,
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
