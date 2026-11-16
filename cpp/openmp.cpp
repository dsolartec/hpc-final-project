// =============================================================================
// openmp.cpp — Versión C++ con OpenMP (paradigm="openmp", workers=N hilos)
//
// Estrategia (memoria compartida):
//   * #pragma omp parallel for sobre las FILAS del tablero en cada sub-paso.
//     Una sola región paralela por sub-paso procesa ambas cepas de cada fila.
//   * Doble buffer (cur/nxt): cada hilo lee solo de cur y escribe solo en sus
//     filas de nxt -> no hay condiciones de carrera ni hace falta sincronizar
//     dentro del sub-paso; la barrera implícita del parallel for separa pasos.
//   * Un generador por fila (ver common.hpp): cada iteración crea su propio
//     mt19937_64 -> no se comparte estado aleatorio entre hilos y el resultado
//     es idéntico al de la versión serial para cualquier número de hilos.
//   * Totales mensuales y casos nuevos con reduction(+:...).
//   * Scheduling: schedule(runtime), por defecto "static". Justificación: todas
//     las filas tienen el mismo número de celdas y el mismo trabajo esperado,
//     así que static reparte bloques contiguos (buena localidad de caché, cero
//     costo de planificación). --schedule dynamic|guided permite medir la
//     alternativa (guía §6.7, pregunta 7).
//
// Hilos: --threads N tiene prioridad; si no se da, se usa OMP_NUM_THREADS.
//
// Compilar:  make openmp
// Ejecutar:  ./openmp --region pacifico --threads 4 --runs 5
//            OMP_NUM_THREADS=4 ./openmp --region pacifico
// =============================================================================
#include <omp.h>

#include "common.hpp"

using namespace hpc;

static double simulate(const RegionData& rd, uint64_t seed, uint64_t run, std::vector<MonthMetrics>& hist) {
    Domain d;
    d.allocate(rd.L, rd.L, 0);
    // Inicialización paralela (no cronometrada); first-touch en el hilo que luego usa la fila.
#pragma omp parallel for schedule(runtime)
    for (int r = 0; r < d.rows; ++r) init_rows(d, r, r + 1, seed, run, rd.p_init);
    hist.assign(rd.months.size(), MonthMetrics{});

    const auto t0 = std::chrono::steady_clock::now();
    for (size_t t = 0; t < rd.months.size(); ++t) {
        const MonthRow& m = rd.months[t];
        const double dt = month_dt(m);
        StepConstants k[N_STRAINS];
        for (int s = 0; s < N_STRAINS; ++s) k[s] = make_step_constants(s, m.temperatura, m.humedad, m.precipitacion, dt);

        int64_t cases_f = 0, cases_v = 0;
        for (int sub = 0; sub < AC_STEPS_PER_MONTH; ++sub) {
            fill_ghosts_local(d);  // 2 filas por tablero: costo O(L), se deja secuencial
#pragma omp parallel for schedule(runtime) reduction(+ : cases_f, cases_v)
            for (int r = 0; r < d.rows; ++r) {
                Rng rng_f(stream_seed(seed, run, t, sub, FALCIPARUM, d.row_offset + r));
                cases_f += step_row(d, FALCIPARUM, r, k[FALCIPARUM], rng_f);
                Rng rng_v(stream_seed(seed, run, t, sub, VIVAX, d.row_offset + r));
                cases_v += step_row(d, VIVAX, r, k[VIVAX], rng_v);
            }
            for (int s = 0; s < N_STRAINS; ++s) d.cur[s].swap(d.nxt[s]);
        }

        int64_t tot[N_TOTALS] = {0};
#pragma omp parallel for schedule(runtime) reduction(+ : tot[:N_TOTALS])
        for (int r = 0; r < d.rows; ++r) accumulate_row_totals(d, r, tot);
        MonthMetrics& mm = hist[t];
        std::copy(std::begin(tot), std::end(tot), mm.totals);
        mm.cases[FALCIPARUM] = cases_f;
        mm.cases[VIVAX] = cases_v;
    }
    const auto t1 = std::chrono::steady_clock::now();
    return std::chrono::duration<double>(t1 - t0).count();
}

int main(int argc, char** argv) {
    const Args a = parse_args(argc, argv, true);
    if (a.threads > 0) omp_set_num_threads(a.threads);

    omp_sched_t kind = omp_sched_static;
    if (a.schedule == "dynamic") kind = omp_sched_dynamic;
    else if (a.schedule == "guided") kind = omp_sched_guided;
    else if (a.schedule != "static") { std::fprintf(stderr, "Scheduling inválido: %s\n", a.schedule.c_str()); return 2; }
    omp_set_schedule(kind, 0);  // chunk 0 = valor por defecto de la implementación

    const int workers = omp_get_max_threads();
    const auto all = load_regions(a.data, a.board_size);
    const std::string paradigm = "openmp";

    for (const RegionData* rd : select_regions(all, a.region)) {
        std::printf("[openmp] región=%s L=%d hilos=%d schedule=%s runs=%d warmup=%d seed=%llu\n", rd->lower.c_str(),
                    rd->L, workers, a.schedule.c_str(), a.runs, a.warmup, (unsigned long long)a.seed);
        std::vector<MonthMetrics> hist;
        for (int w = 0; w < a.warmup; ++w) simulate(*rd, a.seed, 1000000 + w, hist);
        for (int run = 0; run < a.runs; ++run) {
            const double elapsed = simulate(*rd, a.seed, run, hist);
            append_times(a.outdir, paradigm, rd->lower, workers, rd->L, elapsed);
            if (a.metrics) write_metrics(a.outdir, paradigm, *rd, hist, run, a.runs);
            std::printf("[openmp] %s run=%d hilos=%d elapsed=%.4f s\n", rd->lower.c_str(), run, workers, elapsed);
        }
    }
    return 0;
}
