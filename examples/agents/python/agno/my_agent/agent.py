from agno.agent import Agent
from agno.models.openai import OpenAIChat
#from agno.db.sqlite import AsyncSqliteDb

agent = Agent(
    name="Assistant",
    model=OpenAIChat(id="gpt-4.1"),
    #db=AsyncSqliteDb(db_file="my_os.db"),
    instructions=["You are a helpful AI assistant."],
    markdown=True,
)

root_agent = agent