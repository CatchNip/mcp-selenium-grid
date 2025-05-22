from typing import Dict

from pydantic import BaseModel


class BrowserConfig(BaseModel):
    image: str
    port: int
    resources: Dict[str, str]
