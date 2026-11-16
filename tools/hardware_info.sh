#!/usr/bin/env bash
# Registra el hardware y las versiones usadas en las mediciones (guía §6.4). Linux/WSL y macOS.
# Uso (desde la raíz del repo):  bash tools/hardware_info.sh > outputs/hardware.txt
. "$(dirname "$0")/_equipo.sh"
COMPILADOR=$(make -s -C "$(dirname "$0")/../cpp" info 2>/dev/null | tail -1)
CXX_BIN=${COMPILADOR%% |*}
echo "fecha: $(date +%Y-%m-%dT%H:%M:%S)"
echo "equipo: $(hostname)"
if [ "$(uname -s)" = "Darwin" ]; then
  echo "so: macOS $(sw_vers -productVersion) / kernel $(uname -r) ($(uname -m))"
  echo "Model name: $(sysctl -n machdep.cpu.brand_string)"
  echo "CPU(s): $(sysctl -n hw.logicalcpu)"
  echo "Thread(s) per core: $(( $(sysctl -n hw.logicalcpu) / $(sysctl -n hw.physicalcpu) ))"
  echo "nucleos_rendimiento: $(nucleos_rendimiento)"
  echo "nucleos_eficiencia: $(( $(nucleos_fisicos) - $(nucleos_rendimiento) ))"
  echo "memoria: $(( $(sysctl -n hw.memsize) / 1073741824 )) GB"
else
  echo "so: $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") / kernel $(uname -r)"
  lscpu | grep -E 'Model name|^CPU\(s\)|Thread\(s\) per core|Core\(s\) per socket|Socket\(s\)|L[123].? cache' | sed 's/  */ /g'
  echo "nucleos_rendimiento: $(nucleos_rendimiento)"
  echo "nucleos_eficiencia: 0"
  echo "memoria: $(free -h | awk '/Mem:/{print $2}')"
fi
echo "g++: $(${CXX_BIN:-g++} --version 2>/dev/null | head -1)"
echo "mpi: $(mpirun --version 2>/dev/null | head -1)"
echo "python: $(python3 --version 2>&1)"
python3 -c "import numpy, pandas; print('numpy:', numpy.__version__, '/ pandas:', pandas.__version__)" 2>/dev/null
echo "banderas C++: ${COMPILADOR#*| } (-fopenmp en OpenMP)"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | sed 's/^/gpu: /'
else
  echo "gpu: sin GPU NVIDIA en este equipo (CuPy/CUDA se miden aparte)"
fi
