// =============================================================================
// mpi.cpp — Versión C++ con MPI (paradigm="mpi", workers=P procesos)
//
// Estrategia (memoria distribuida, descomposición de dominio 1D por franjas):
//   * El tablero L x L se divide en P franjas de filas contiguas. Si L no es
//     divisible por P, los primeros (L mod P) procesos reciben una fila más
//     (desbalance máximo de 1 fila).
//   * Cada proceso guarda su franja con 2 filas fantasma (arriba y abajo).
//     Antes de cada sub-paso se intercambian los bordes con MPI_Sendrecv
//     (comunicación punto a punto, sin interbloqueo). Toroide: el vecino de
//     arriba del rank 0 es el rank P-1 y el de abajo del rank P-1 es el rank 0.
//   * Se intercambia lo que necesita la vecindad de Moore, para ambas cepas:
//     humanos infectados (I_h), mosquitos infectados (I_m) y mosquitos
//     susceptibles (S_m); con S_m + I_m cada proceso obtiene los mosquitos vivos.
//     Son 6 filas de L enteros por dirección y sub-paso, en un solo mensaje.
//   * Las columnas no se reparten, así que su periodicidad es local.
//   * Totales mensuales: suma local + MPI_Reduce(SUM) al rank 0.
//   * Tiempo: MPI_Barrier antes y después del bucle; se reporta el tiempo
//     MÁXIMO entre procesos (MPI_Reduce con MPI_MAX). Solo el rank 0 escribe.
//   * Generador por fila global (common.hpp): el resultado es idéntico al de
//     la versión serial para cualquier P.
//   * Cada proceso lee el CSV de entrada (1 020 filas, fuera del cronómetro).
//
// Compilar:  make mpi
// Ejecutar:  mpirun -np 4 ./mpi --region pacifico --runs 5   (P <= núcleos físicos)
// =============================================================================
// Evita los bindings C++ obsoletos de OpenMPI/MPICH (generan warnings en sus headers).
#define OMPI_SKIP_MPICXX 1
#define MPICH_SKIP_MPICXX 1
#include <mpi.h>

#include "common.hpp"

using namespace hpc;

struct Strip { int rows, offset; };

// Reparto de filas: los primeros (L mod P) procesos reciben una fila extra.
static Strip strip_for(int L, int P, int rank) {
    const int base = L / P, extra = L % P;
    return {base + (rank < extra ? 1 : 0), rank * base + std::min(rank, extra)};
}

// Intercambio de filas fantasma (I_h, I_m, S_m de las dos cepas).
static void exchange_ghosts(Domain& d, int up, int down, std::vector<int32_t>& sbuf, std::vector<int32_t>& rbuf) {
    const int L = d.L;
    const int count = 6 * L;
    auto pack = [&](int r) {
        int k = 0;
        for (int s = 0; s < N_STRAINS; ++s)
            for (const Board* b : {&d.cur[s].Ih, &d.cur[s].Im, &d.cur[s].Sm}) {
                std::copy(b->begin() + d.idx(r, 0), b->begin() + d.idx(r, 0) + L, sbuf.begin() + k);
                k += L;
            }
    };
    auto unpack = [&](int r) {
        int k = 0;
        for (int s = 0; s < N_STRAINS; ++s)
            for (Board* b : {&d.cur[s].Ih, &d.cur[s].Im, &d.cur[s].Sm}) {
                std::copy(rbuf.begin() + k, rbuf.begin() + k + L, b->begin() + d.idx(r, 0));
                k += L;
            }
    };
    // 1) Mi primera fila sube al vecino de arriba; recibo la primera fila del de abajo -> fantasma inferior.
    pack(0);
    MPI_Sendrecv(sbuf.data(), count, MPI_INT32_T, up, 0, rbuf.data(), count, MPI_INT32_T, down, 0,
                 MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    unpack(d.rows);
    // 2) Mi última fila baja al vecino de abajo; recibo la última fila del de arriba -> fantasma superior.
    pack(d.rows - 1);
    MPI_Sendrecv(sbuf.data(), count, MPI_INT32_T, down, 1, rbuf.data(), count, MPI_INT32_T, up, 1,
                 MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    unpack(-1);
}

// Simula una réplica; devuelve el tiempo máximo entre procesos (válido en el rank 0).
static double simulate(const RegionData& rd, uint64_t seed, uint64_t run, int rank, int P,
                       std::vector<MonthMetrics>& hist) {
    const Strip st = strip_for(rd.L, P, rank);
    Domain d;
    d.allocate(rd.L, st.rows, st.offset);
    init_rows(d, 0, d.rows, seed, run, rd.p_init);
    hist.assign(rd.months.size(), MonthMetrics{});
    const int up = (rank - 1 + P) % P, down = (rank + 1) % P;
    std::vector<int32_t> sbuf(6 * rd.L), rbuf(6 * rd.L);

    MPI_Barrier(MPI_COMM_WORLD);
    const auto t0 = std::chrono::steady_clock::now();
    for (size_t t = 0; t < rd.months.size(); ++t) {
        const MonthRow& m = rd.months[t];
        const double dt = month_dt(m);
        StepConstants k[N_STRAINS];
        for (int s = 0; s < N_STRAINS; ++s) k[s] = make_step_constants(s, m.temperatura, m.humedad, m.precipitacion, dt);

        int64_t local[N_TOTALS + N_STRAINS] = {0};  // 10 totales + 2 casos
        for (int sub = 0; sub < AC_STEPS_PER_MONTH; ++sub) {
            exchange_ghosts(d, up, down, sbuf, rbuf);
            for (int s = 0; s < N_STRAINS; ++s) {
                for (int r = 0; r < d.rows; ++r) {
                    Rng rng(stream_seed(seed, run, t, sub, s, d.row_offset + r));
                    local[N_TOTALS + s] += step_row(d, s, r, k[s], rng);
                }
                d.cur[s].swap(d.nxt[s]);
            }
        }
        for (int r = 0; r < d.rows; ++r) accumulate_row_totals(d, r, local);
        int64_t global[N_TOTALS + N_STRAINS] = {0};
        MPI_Reduce(local, global, N_TOTALS + N_STRAINS, MPI_INT64_T, MPI_SUM, 0, MPI_COMM_WORLD);
        if (rank == 0) {
            std::copy(global, global + N_TOTALS, hist[t].totals);
            hist[t].cases[FALCIPARUM] = global[N_TOTALS + FALCIPARUM];
            hist[t].cases[VIVAX] = global[N_TOTALS + VIVAX];
        }
    }
    MPI_Barrier(MPI_COMM_WORLD);
    const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    double max_elapsed = 0.0;
    MPI_Reduce(&elapsed, &max_elapsed, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
    return max_elapsed;
}

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank = 0, P = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &P);

    const Args a = parse_args(argc, argv, false, rank != 0);
    const auto all = load_regions(a.data, a.board_size);
    const std::string paradigm = "mpi";

    for (const RegionData* rd : select_regions(all, a.region)) {
        if (P > rd->L) {
            if (rank == 0) std::fprintf(stderr, "ERROR: P=%d > L=%d filas\n", P, rd->L);
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
        if (rank == 0)
            std::printf("[mpi] región=%s L=%d procesos=%d filas/proceso=%d..%d runs=%d warmup=%d seed=%llu\n",
                        rd->lower.c_str(), rd->L, P, rd->L / P, (rd->L + P - 1) / P, a.runs, a.warmup,
                        (unsigned long long)a.seed);
        std::vector<MonthMetrics> hist;
        for (int w = 0; w < a.warmup; ++w) simulate(*rd, a.seed, 1000000 + w, rank, P, hist);
        for (int run = 0; run < a.runs; ++run) {
            const double elapsed = simulate(*rd, a.seed, run, rank, P, hist);
            if (rank == 0) {  // escritura después del cronómetro, solo rank 0
                append_times(a.outdir, paradigm, rd->lower, P, rd->L, elapsed);
                if (a.metrics) write_metrics(a.outdir, paradigm, *rd, hist, run, a.runs);
                std::printf("[mpi] %s run=%d procesos=%d elapsed=%.4f s\n", rd->lower.c_str(), run, P, elapsed);
                std::fflush(stdout);
            }
        }
    }
    MPI_Finalize();
    return 0;
}
