# Proyecto final de Computación de Alto Desempeño

## Integrantes

- Daniel Solarte ([@dsolartec](https://github.com/dsolartec))
- Alejandro Garcés ([@SamuelMarroquin2009-12](https://github.com/SamuelMarroquin2009-12))
- Juan Esteban Ramirez ([@juanes779](https://github.com/juanes779))

## Contexto del problema

La malaria (paludismo) es una afección parasitaria transmitida por mosquitos hembra del género Anopheles que exhibe una acentuada heterogeneidad espaciotemporal en Colombia. La transmisión se concentra en focos endémicos y epidémicos específicos (como la Costa Pacífica, Urabá-Bajo Cauca-Alto San Jorge, Amazonía y Orinoquía), regulada por gradientes climáticos, regímenes hidrológicos y dinámicas de movilidad poblacional.

El modelo utilizado para la simulación del contagio entre mosquitos y humanos para cada cepa de malaria (P. Vivax y P. Falciparum) es el Ross-Macdonald, este describe el comportamiento de esa interacción en un rango de días en base al clima de la región analizada (Se adaptó a que fuera mensual).

Se están analizando dos cepas diferentes porque una de ellas vive en temperaturas altas (P. Vivax) y otra en temperaturas bajas (P. Falciparum) dando como resultado que una cepa predomina sobre la otra en cada región del país, pero la que predomina a nivel general es la P. Vivax.

Los datos utilizados para la simulación corresponden a los entregados por la Guía de Atención Médica (GAM) del Ministerio de Salud de Colombia desde Enero de 2007 hasta Diciembre de 2023.

## Python

### Pre-requisitos

- Python >=3.14 - [Guía de Instalación](https://wiki.python.org/python/getting-started/BeginnersGuide/Download.html)
- Poetry >=2.4.1 - [Documentación](https://python-poetry.org/docs/)

```bash
pipx install poetry==2.4.1
```
> Comando para instalar Poetry usando PIP

### Ejecución

Toda la ejecución del programa para Python está en el [README.md](./python/README.md) de la carpeta de Python, los comandos debes ejecutarlos dentro de esa carpeta, para dirigirte a ella puedes usar `cd python` en tu terminal.

## C++

TODO: Hacer la parte de C++

## Formato de los resultados (Carpeta `outputs`)

### Archivo de tiempos de ejecución (`times.csv`)

En este archivo se consolidarán todas las ejecuciones que se realicen utilizando el proyecto (tanto en Python como en C++ y sus variantes paralelas), siguiendo este esquema:

| Columna | Descripción |
|---|---|
| execution_timestamp | Timestamp UNIX del momento en que finaliza la simulación |
| language | Lenguaje de programación empleado (`python`, `cpp`) |
| paradigm | Paradigma computacional (`pure`, `numpy`, `cupy`, `multiprocessing`, `openmp`, `mpi`, etc.) |
| region | Región geográfica evaluada (`amazonia`, `andina`, `caribe`, `orinoquia`, `pacifico`) |
| workers | Cantidad efectiva de hilos o procesos de cómputo utilizados (1 para secuencial monoproceso) |
| board_size | Tamaño del lado del tablero ($L$), es decir, si el valor es 30, el tablero es de 30x30 celdas |
| iterations | Cantidad de iteraciones mensuales simuladas del modelo SIRS (204 meses) |
| elapsed_time | Tiempo transcurrido de simulación en segundos (excluyendo I/O y renderizado) |

### Animaciones

Se guardará cada animación resultante en formato HTML para poder visualizarla con botones interactivos, esta se hará en base a los resultados de cada ejecución.

> **NOTA:** Solo se guardará una animación por librería y región.
