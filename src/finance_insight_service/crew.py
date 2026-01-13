import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool, SerpApiGoogleSearchTool, SerperDevTool


@CrewBase
class FinanceInsightResearchCrew:
    """Research crew for finance news discovery and synthesis."""

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

    @task
    def research_news_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_news_task"],
            agent=self.researcher(),
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Finance Insight Research crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


def _build_search_tool():
    if os.getenv("SERPAPI_API_KEY"):
        return SerpApiGoogleSearchTool()
    if os.getenv("SERPER_API_KEY"):
        return SerperDevTool(search_type="news", n_results=10)
    raise ValueError("Set SERPER_API_KEY or SERPAPI_API_KEY to enable news search.")
