# Proyecto final de Computación de Alto Desempeño (Python)

> **NOTA:** TODOS los comandos descritos en este archivo deben ejecutarse dentro de la carpeta `python/`, asegúrate que estés dentro de la carpeta antes de empezar.

## Instalación de dependencias

Para instalar las dependencias del proyecto asegúrate de ejecutar el siguiente comando en tu terminal:

```bash
poetry install
```

## Ejecución secuencial

Para ejecutar el modelo SIR que usa código puro en Python (Secuencial), utiliza el siguiente comando:

```bash
poetry run python main.py pure
```

## Ejecución paralelo CPU

TODO: Elegir multiprocessing, joblib o Dask <br>
TODO: Hacer guía para paralelo CPU

## Ejecución con NumPy

Para ejecutar el modelo SIR que usa la librería de NumPy, utiliza el siguiente comando:

```bash
poetry run python main.py numpy
```

### Argumentos opcionales

| Argumento | Descripción | Valores aceptados | Valor por defecto |
|---|---|---|---|
| `region` | Región a utilizar en el model | `Amazonia`, `Andina`, `Caribe`, `Orinoquia`, `Pacifico` o `todo` | Pacifico |

> **Modo de uso:** `poetry run main.py numpy --region andina`

### Resultados generados

Este comando genera las gráficas animadas de cada uno de los 10 tableros SIR de cada región evaluada, estos estarán ubicados en `../outputs/animations/numpy_{amazonia,andina,caribe,orinoquia,pacifico}.html`. Igualmente, va registrando el tiempo de ejecución en el archivo `outputs/times.csv` con el _type_ `python_numpy_{region}`.

## Ejecución con CuPy

TODO: Hacer guía para CuPy
