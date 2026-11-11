# Proyecto final de Computación de Alto Desempeño (Python)

> **NOTA:** TODOS los comandos descritos en este archivo deben ejecutarse dentro de la carpeta `python/`, asegúrate que estés dentro de la carpeta antes de empezar.

## Instalación de dependencias

Para instalar las dependencias del proyecto asegúrate de ejecutar el siguiente comando en tu terminal:

```bash
poetry install
```

## Ejecución secuencial

```bash
poetry run python main.py pure
```

## Ejecución paralelo CPU

TODO: Elegir multiprocessing, joblib o Dask <br>
TODO: Hacer guía para paralelo CPU

## Ejecución con NumPy

```bash
poetry run python main.py numpy
```

### Argumentos opcionales

| Argumento | Descripción | Valores aceptados | Valor por defecto |
|---|---|---|---|
| `region` | Región a utilizar en el model | `Amazonia`, `Andina`, `Caribe`, `Orinoquia` o `Pacifico` | Pacifico |

> **Modo de uso:** `poetry run main.py numpy --region andina`

## Ejecución con CuPy

TODO: Hacer guía para CuPy
