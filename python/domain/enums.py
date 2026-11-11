from enum import Enum


class ModelType(Enum):
    COLOMBIA = "Nivel Nacional"
    DEPARTMENT = "Nivel Departamental"
    CITY = "Nivel Municipal"


class MalariaType(Enum):
    VIVAX = "vivax"
    FALCIPARUM = "falciparum"
