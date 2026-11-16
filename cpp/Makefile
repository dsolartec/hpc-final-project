# Makefile — implementaciones C++ del autómata celular (serial, OpenMP, MPI)
#
#   make            compila las tres versiones
#   make secuencial | openmp | mpi
#   make info       muestra el compilador y las banderas que se usarán
#   make clean
#
# Linux / WSL:  g++ (C++17, OpenMP) y OpenMPI:
#                   sudo apt install build-essential openmpi-bin libopenmpi-dev
# macOS:        el g++ de Apple es clang y NO trae OpenMP; se usa el GCC de Homebrew:
#                   brew install gcc open-mpi
#               El Makefile lo detecta solo (g++-NN) y hace que mpicxx lo use (OMPI_CXX).
#               Para forzar otro compilador:  make CXX=g++-14
#               Si el compilador no acepta -mcpu=native:  make NATIVE=
UNAME := $(shell uname -s)
ifeq ($(UNAME),Darwin)
  ifeq ($(origin CXX),default)
    BREW_GXX := $(shell ls "$$(brew --prefix 2>/dev/null)"/bin/g++-[0-9]* 2>/dev/null | sort -V | tail -1)
    CXX := $(if $(BREW_GXX),$(BREW_GXX),g++)
  endif
  export OMPI_CXX := $(CXX)
  NATIVE ?= -mcpu=native
else
  NATIVE ?= -march=native
endif
MPICXX   ?= mpicxx
CXXFLAGS ?= -O3 $(NATIVE) -std=c++17 -Wall -Wextra -Wpedantic
BINARIOS := secuencial openmp mpi openmp_glibc_lgamma

all: secuencial openmp mpi

secuencial: secuencial.cpp common.hpp
	$(CXX) $(CXXFLAGS) secuencial.cpp -o secuencial

openmp: openmp.cpp common.hpp
	$(CXX) $(CXXFLAGS) -fopenmp openmp.cpp -o openmp

mpi: mpi.cpp common.hpp
	$(MPICXX) $(CXXFLAGS) mpi.cpp -o mpi

# Variante SIN la corrección de lgamma (usa lgamma de la biblioteca de C con estado global).
# Solo para reproducir la medición de contención entre hilos del informe.
openmp_glibc_lgamma: openmp.cpp common.hpp
	$(CXX) $(CXXFLAGS) -fopenmp -DHPC_GLIBC_LGAMMA openmp.cpp -o openmp_glibc_lgamma

info:
	@echo "$(CXX) | $(CXXFLAGS)"

clean:
	$(RM) $(BINARIOS)

.PHONY: all clean info
