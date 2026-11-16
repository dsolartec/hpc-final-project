// =============================================================================
// secuencial.cpp — Versión C++ secuencial (paradigm="serial", workers=1)
//
// Línea base compilada para el speedup de OpenMP, MPI y GPU (guía §6.3).
// Traducción directa de python/adapters/utils_pure.py; ver common.hpp.
//
// Compilar:  make secuencial
// Ejecutar:  ./secuencial --region amazonia --runs 5 --seed 12345
// =============================================================================
#include "common.hpp"

using namespace hpc;

// Simula una réplica completa; devuelve el tiempo del bucle de 204 meses.
static double simulate(const RegionData& rd, uint64_t seed, uint64_t run, std::vector<MonthMetrics>& hist) {
    Domain d;
    d.allocate(rd.L, rd.L, 0);
    init_rows(d, 0, d.rows, seed, run, rd.p_init);  // inicialización: fuera del cronómetro
    hist.assign(rd.months.size(), MonthMetrics{});

    const auto t0 = std::chrono::steady_clock::now();
    for (size_t t = 0; t < rd.months.size(); ++t) {
        const MonthRow& m = rd.months[t];
        const double dt = month_dt(m);
        StepConstants k[N_STRAINS];
        for (int s = 0; s < N_STRAINS; ++s) k[s] = make_step_constants(s, m.temperatura, m.humedad, m.precipitacion, dt);

        int64_t cases[N_STRAINS] = {0, 0};
        for (int sub = 0; sub < AC_STEPS_PER_MONTH; ++sub) {
            fill_ghosts_local(d);  // toroide: copia de filas de borde
            for (int s = 0; s < N_STRAINS; ++s) {
                for (int r = 0; r < d.rows; ++r) {
                    Rng rng(stream_seed(seed, run, t, sub, s, d.row_offset + r));
                    cases[s] += step_row(d, s, r, k[s], rng);
                }
                d.cur[s].swap(d.nxt[s]);  // doble buffer
            }
        }
        MonthMetrics& mm = hist[t];
        std::fill(std::begin(mm.totals), std::end(mm.totals), 0);
        for (int r = 0; r < d.rows; ++r) accumulate_row_totals(d, r, mm.totals);
        mm.cases[0] = cases[0]; mm.cases[1] = cases[1];
    }
    const auto t1 = std::chrono::steady_clock::now();
    return std::chrono::duration<double>(t1 - t0).count();
}

int main(int argc, char** argv) {
    const Args a = parse_args(argc, argv, false);
    const auto all = load_regions(a.data, a.board_size);
    const std::string paradigm = "serial";

    for (const RegionData* rd : select_regions(all, a.region)) {
        std::printf("[serial] región=%s L=%d celdas=%d runs=%d warmup=%d seed=%llu\n", rd->lower.c_str(), rd->L,
                    rd->L * rd->L, a.runs, a.warmup, (unsigned long long)a.seed);
        std::vector<MonthMetrics> hist;
        for (int w = 0; w < a.warmup; ++w) simulate(*rd, a.seed, 1000000 + w, hist);  // calentamiento, no se registra
        for (int run = 0; run < a.runs; ++run) {
            const double elapsed = simulate(*rd, a.seed, run, hist);
            // Todo lo siguiente ocurre DESPUÉS de detener el cronómetro.
            append_times(a.outdir, paradigm, rd->lower, 1, rd->L, elapsed);
            if (a.metrics) write_metrics(a.outdir, paradigm, *rd, hist, run, a.runs);
            std::printf("[serial] %s run=%d elapsed=%.4f s\n", rd->lower.c_str(), run, elapsed);
        }
    }
    return 0;
}
