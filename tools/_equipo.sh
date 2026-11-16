# Funciones comunes de los scripts (Linux/WSL y macOS).
# Se usa con:  . "$(dirname "$0")/_equipo.sh"

# Núcleos físicos del equipo (no hilos lógicos).
nucleos_fisicos() {
  if [ "$(uname -s)" = "Darwin" ]; then
    sysctl -n hw.physicalcpu
  elif command -v lscpu >/dev/null 2>&1; then
    lscpu -p=CORE,SOCKET | grep -v '^#' | sort -u | wc -l | tr -d ' '
  else
    getconf _NPROCESSORS_ONLN
  fi
}

# En CPU heterogéneas (Apple Silicon): solo los núcleos de alto rendimiento.
nucleos_rendimiento() {
  if [ "$(uname -s)" = "Darwin" ] && sysctl -n hw.perflevel0.physicalcpu >/dev/null 2>&1; then
    sysctl -n hw.perflevel0.physicalcpu
  else
    nucleos_fisicos
  fi
}

MPIRUN="mpirun"
if [ "$(id -u)" = "0" ]; then MPIRUN="mpirun --allow-run-as-root"; fi
