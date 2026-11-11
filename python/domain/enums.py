from enum import Enum


class ACBoardType(Enum):
    HUMANS_FALCIPARUM_SUSCEPTIBLE = ("humans_falciparum_susceptible_count_board", "Humanos Susceptibles (Falciparum)", "YlGnBu")
    HUMANS_FALCIPARUM_INFECTED = ("humans_falciparum_infected_count_board", "Humanos Infectados (Falciparum)", "YlOrRd")
    HUMANS_FALCIPARUM_RECOVERED = ("humans_falciparum_recovered_count_board", "Humanos Recuperados (Falciparum)", "Greens")
    MOSQUITOES_FALCIPARUM_SUSCEPTIBLE = ("mosquitoes_falciparum_susceptible_count_board", "Mosquitos Susceptibles (Falciparum)", "PuBu")
    MOSQUITOES_FALCIPARUM_INFECTED = ("mosquitoes_falciparum_infected_count_board", "Mosquitos Infectados (Falciparum)", "OrRd")
    HUMANS_VIVAX_SUSCEPTIBLE = ("humans_vivax_susceptible_count_board", "Humanos Susceptibles (Vivax)", "YlGnBu")
    HUMANS_VIVAX_INFECTED = ("humans_vivax_infected_count_board", "Humanos Infectados (Vivax)", "YlOrRd")
    HUMANS_VIVAX_RECOVERED = ("humans_vivax_recovered_count_board", "Humanos Recuperados (Vivax)", "Greens")
    MOSQUITOES_VIVAX_SUSCEPTIBLE = ("mosquitoes_vivax_susceptible_count_board", "Mosquitos Susceptibles (Vivax)", "PuBu")
    MOSQUITOES_VIVAX_INFECTED = ("mosquitoes_vivax_infected_count_board", "Mosquitos Infectados (Vivax)", "OrRd")

    @property
    def key(self) -> str:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]

    @property
    def cmap(self) -> str:
        return self.value[2]


class ModelType(Enum):
    COLOMBIA = "Nivel Nacional"
    DEPARTMENT = "Nivel Departamental"
    CITY = "Nivel Municipal"


class MalariaType(Enum):
    VIVAX = "vivax"
    FALCIPARUM = "falciparum"
