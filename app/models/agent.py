from pydantic import BaseModel
from typing import List, Optional

class AgentConfig(BaseModel):
    name: str
    role: str
    purpose: str
    instructions: List[str]
    capabilities: List[str]
    welcome_message: str
    tone: str
    knowledge_base: List[str]
    sample_prompts: List[str]
    schedule_enabled: bool = False
    frequency: Optional[str] = None
    time: Optional[str] = None
    output_method: Optional[str] = None
    published: bool = False
