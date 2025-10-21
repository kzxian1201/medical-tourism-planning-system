from pydantic import BaseModel, Field
from typing import Optional # 导入 Optional

class TaskflowAITaskDefinition(BaseModel):
    """
    Schema for defining a task compatible with TaskflowAI's Task.create() method.
    """
    description: str = Field(
        ...,
        description="A detailed and clear description of the task to be performed by an agent. "
                    "This should include all necessary context and constraints."
    )
    expected_output: str = Field(
        ...,
        description="A clear and concise description of the expected outcome or result of the task. "
                    "This should specify what information or format the output should be in."
    )
