from pydantic import BaseModel


class ConfiguracionCreate(BaseModel):
    clave: str
    valor: str


class ConfiguracionUpdate(BaseModel):
    valor: str


class ConfiguracionOut(BaseModel):
    clave: str
    valor: str
