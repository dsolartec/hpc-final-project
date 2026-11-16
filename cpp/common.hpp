// =============================================================================
// common.hpp — Código compartido por secuencial.cpp, openmp.cpp y mpi.cpp
//
// Port directo de python/adapters/utils_pure.py (NO de la versión NumPy) del
// autómata celular estocástico 2D SIRS (humanos) – SI (mosquitos), modelo
// Ross-Macdonald, especificado en AGENTS.md.
//
// Contenido:
//   1. Parámetros (copiados de python/domain/constants.py)
//   2. Funciones del modelo (factores climáticos y probabilidades)
//   3. Generador de números aleatorios y muestreo Binomial
//   4. Tableros (int32, L x L, con 2 filas fantasma) e inicialización
//   5. Regla de evolución de una fila (un sub-paso, una cepa)
//   6. Lectura de datos (CSV) y escritura de resultados (times.csv, métricas)
//   7. Argumentos de línea de comandos comunes
//
// ---------------------------------------------------------------------------
// GENERADOR Y SEMILLAS (decisión documentada)
// ---------------------------------------------------------------------------
// Generador: std::mt19937_64; muestreo: std::binomial_distribution<int>.
//
// En lugar de "un generador por hilo/proceso sembrado con semilla + id", cada
// FILA del tablero tiene su propio flujo, sembrado con un hash SplitMix64 de
//      (semilla_base, run, mes, sub-paso, cepa, fila_global)
// (en la inicialización: mes = INIT_TAG). Justificación:
//   * Los flujos siguen siendo independientes entre hilos/procesos (como pide
//     la guía: "flujos independientes por proceso, hilo o realización"), porque
//     dos filas nunca comparten flujo.
//   * El resultado NO depende del número de hilos ni de procesos ni del
//     scheduling: serial, OpenMP(p) y MPI(p) producen EXACTAMENTE el mismo CSV
//     de métricas para la misma semilla. Así la corrección de la paralelización
//     se demuestra con una comparación exacta (diff), y la validación
//     estadística (AGENTS.md §9.2) queda solo para C++ vs. Python.
//   * Réplicas Monte Carlo distintas (run distinto) usan flujos distintos, así
//     que no se repiten realizaciones (error frecuente citado en la guía §5.7).
//   * Costo: re-sembrar un mt19937_64 por fila y sub-paso (~312 palabras de
//     estado) es despreciable frente a los ~8 muestreos Binomiales por celda.
// =============================================================================
#pragma once

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <sys/stat.h>
#include <vector>

// ---------------------------------------------------------------------------
// lgamma reentrante (corrección de rendimiento medida, ver README / informe)
// ---------------------------------------------------------------------------
// std::binomial_distribution (libstdc++) llama a lgamma() de glibc al preparar
// cada muestreo. lgamma() escribe la variable GLOBAL `signgam`, de modo que con
// varios hilos esa línea de caché rebota entre núcleos (contención por
// escrituras compartidas). Redefinimos lgamma() con lgamma_r(), que devuelve el
// signo en una variable local: mismo valor numérico, sin estado compartido.
// Medido en amazonia, OpenMP 4 hilos: 1.1 s -> 0.81 s; resultados idénticos.
// Compilar con -DHPC_GLIBC_LGAMMA desactiva la corrección (make openmp_glibc_lgamma).
// Se aplica a las tres versiones para que la comparación sea justa.
// En glibc, lgamma está declarada noexcept; en macOS no. La macro mantiene la
// redefinición compatible con ambas bibliotecas de C.
#if defined(__GLIBC__)
#define HPC_C_NOEXCEPT noexcept
#else
#define HPC_C_NOEXCEPT
#endif
#ifndef HPC_GLIBC_LGAMMA
extern "C" double lgamma_r(double, int*) HPC_C_NOEXCEPT;
extern "C" double lgamma(double x) HPC_C_NOEXCEPT {
    int sign = 0;
    return lgamma_r(x, &sign);
}
#endif

namespace hpc {

// =============================================================================
// 1. PARÁMETROS (python/domain/constants.py)
// =============================================================================
constexpr int    AC_CELL_POPULATION            = 1000;   // N_H
constexpr int    AC_MAX_MOSQUITOES_PER_CELL    = 2000;   // K_M
constexpr double AC_BITING_RATE                = 0.30;   // a
constexpr double AC_MOSQUITO_MAX_AGE_DAYS      = 21.0;   // 1/mu_m
constexpr double AC_MOSQUITO_WEATHER_DENSITY   = 0.12;   // beta_clima
constexpr double AC_MOSQUITO_NEIGHBORS_DENSITY = 0.04;   // beta_vecinos
constexpr double AC_NEIGHBOR_COUPLING          = 0.25;   // alpha
constexpr int    AC_STEPS_PER_MONTH            = 4;
constexpr int    ITERATIONS                    = 204;    // meses 2007-01 .. 2023-12

struct StrainParams {
    const char* name;
    double t_min, t_opt, t_sigma;
    double prob_mosquito_to_human;  // b
    double prob_human_to_mosquito;  // c
    double recuperation_days;       // tau_rec
    double immunity_loss_days;      // tau_imm
    double relapse_rate;            // rho_relapse
};

constexpr int FALCIPARUM = 0;
constexpr int VIVAX      = 1;
constexpr int N_STRAINS  = 2;

inline const StrainParams STRAIN_PARAMS[N_STRAINS] = {
    {"falciparum", 18.0, 28.0, 4.5, 0.35, 0.30, 14.0,  90.0, 0.0},
    {"vivax",      15.0, 26.0, 5.0, 0.30, 0.40, 21.0, 120.0, 0.0015},
};

// =============================================================================
// 2. FUNCIONES DEL MODELO (utils_pure.py, sección 1)
// =============================================================================
inline double clip01(double x) { return std::max(0.0, std::min(1.0, x)); }

inline double calc_thermal_factor(double T, double t_min, double t_opt, double t_sigma) {
    if (t_min < T && T < 38.0)
        return std::exp(-((T - t_opt) * (T - t_opt)) / (2.0 * t_sigma * t_sigma));
    return 0.0;
}
inline double calc_humidity_factor(double H) { return 1.0 / (1.0 + std::exp(-0.15 * (H - 65.0))); }
inline double calc_precipitation_factor(double P) { return std::min(1.0, std::max(0.05, P / 200.0)); }

inline double calc_infection_probability(double contact_rate, double effective_exposure, double dt) {
    const double rate = clip01(contact_rate);
    const double exponent = effective_exposure * dt;
    if (exponent <= 0.0 || rate <= 0.0) return 0.0;
    if (rate >= 1.0) return 1.0;
    return clip01(1.0 - std::pow(1.0 - rate, exponent));
}
inline double calc_recovery_probability(double dt, double days) {
    return days <= 0.0 ? 1.0 : clip01(dt / days);
}
inline double calc_immunity_loss_probability(double dt, double days) {
    return days <= 0.0 ? 1.0 : clip01(dt / days);
}
inline double calc_relapse_probability(double dt, double rate) {
    if (rate <= 0.0) return 0.0;
    return clip01(1.0 - std::pow(1.0 - std::min(1.0, rate), dt));
}
inline double calc_mosquito_death_probability(double dt) {
    return clip01(dt / AC_MOSQUITO_MAX_AGE_DAYS);
}
inline double calc_effective_exposure(double local_val, double neighbor_mean) {
    return ((1.0 - AC_NEIGHBOR_COUPLING) * local_val + AC_NEIGHBOR_COUPLING * neighbor_mean)
           / static_cast<double>(AC_CELL_POPULATION);
}

// Constantes de una cepa para un sub-paso (dependen solo del clima del mes y de dt).
struct StepConstants {
    double climate_suitability;  // Phi_s
    double rate_m_to_h;
    double rate_h_to_m;
    double p_recover_h;
    double p_loss_imm_h;
    double p_relapse;
    double p_death_m;
    double dt;
    bool   has_relapse;
};

inline StepConstants make_step_constants(int strain, double T, double H, double P, double dt) {
    const StrainParams& sp = STRAIN_PARAMS[strain];
    const double f_t = calc_thermal_factor(T, sp.t_min, sp.t_opt, sp.t_sigma);
    StepConstants k{};
    k.climate_suitability = f_t * calc_humidity_factor(H) * calc_precipitation_factor(P);
    k.rate_m_to_h  = clip01(AC_BITING_RATE * sp.prob_mosquito_to_human);
    k.rate_h_to_m  = clip01(AC_BITING_RATE * sp.prob_human_to_mosquito * f_t);
    k.p_recover_h  = calc_recovery_probability(dt, sp.recuperation_days);
    k.p_loss_imm_h = calc_immunity_loss_probability(dt, sp.immunity_loss_days);
    k.p_relapse    = calc_relapse_probability(dt, sp.relapse_rate);
    k.p_death_m    = calc_mosquito_death_probability(dt);
    k.dt           = dt;
    k.has_relapse  = sp.relapse_rate > 0.0;
    return k;
}

// =============================================================================
// 3. GENERADOR Y MUESTREO BINOMIAL
// =============================================================================
using Rng = std::mt19937_64;

inline uint64_t splitmix64(uint64_t x) {
    x += 0x9E3779B97F4A7C15ULL;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
    return x ^ (x >> 31);
}

constexpr uint64_t INIT_TAG = 0xFFFFFFFFULL;  // "mes" usado en la inicialización

// Semilla del flujo de una fila: hash de (semilla, run, mes, sub-paso, cepa, fila).
inline uint64_t stream_seed(uint64_t seed, uint64_t run, uint64_t month, uint64_t substep,
                            uint64_t strain, uint64_t row) {
    uint64_t h = splitmix64(seed);
    h = splitmix64(h ^ run);
    h = splitmix64(h ^ month);
    h = splitmix64(h ^ substep);
    h = splitmix64(h ^ strain);
    h = splitmix64(h ^ row);
    return h;
}

// Igual que ac_sample_binomial de utils_pure.py: n<=0 o p<=0 -> 0; p>=1 -> n.
inline int sample_binomial(Rng& rng, int n, double p) {
    if (n <= 0 || p <= 0.0) return 0;
    if (p >= 1.0) return n;
    std::binomial_distribution<int> d(n, p);
    return d(rng);
}

// =============================================================================
// 4. TABLEROS E INICIALIZACIÓN
// =============================================================================
// Cada tablero local tiene (rows + 2) filas de L columnas: la fila 0 y la fila
// rows+1 son filas fantasma (copia de las vecinas, periódicas). Las filas reales
// van de 1 a rows. Serial/OpenMP usan rows = L y rellenan los fantasmas
// copiando (toroide); MPI usa una franja y los rellena con MPI_Sendrecv.
using Board = std::vector<int32_t>;

struct StrainBoards {
    Board Sh, Ih, Rh, Sm, Im;
    void resize(size_t n) { Sh.assign(n, 0); Ih.assign(n, 0); Rh.assign(n, 0); Sm.assign(n, 0); Im.assign(n, 0); }
    void swap(StrainBoards& o) { Sh.swap(o.Sh); Ih.swap(o.Ih); Rh.swap(o.Rh); Sm.swap(o.Sm); Im.swap(o.Im); }
};

struct Domain {
    int L = 0;           // lado global del tablero
    int rows = 0;        // filas reales locales
    int row_offset = 0;  // fila global de la primera fila local
    StrainBoards cur[N_STRAINS], nxt[N_STRAINS];  // doble buffer
    std::vector<int> c_prev, c_next;              // columnas vecinas (toroide)

    void allocate(int L_, int rows_, int offset_) {
        L = L_; rows = rows_; row_offset = offset_;
        const size_t n = static_cast<size_t>(rows + 2) * L;
        for (int s = 0; s < N_STRAINS; ++s) { cur[s].resize(n); nxt[s].resize(n); }
        c_prev.resize(L); c_next.resize(L);
        for (int c = 0; c < L; ++c) { c_prev[c] = (c - 1 + L) % L; c_next[c] = (c + 1) % L; }
    }
    // índice de la fila local r (0..rows-1), columna c
    inline size_t idx(int r, int c) const { return static_cast<size_t>(r + 1) * L + c; }
};

// L = max(1, ceil(sqrt(P0 / 1000)))
inline int board_size_from_population(double p0) {
    return std::max(1, static_cast<int>(std::ceil(std::sqrt(p0 / AC_CELL_POPULATION))));
}

// Inicializa las filas locales (ac_generate_initial_boards de utils_pure.py).
// Cada fila global tiene su propio flujo por cepa, así que el tablero global es
// idéntico sin importar cómo se reparta.
inline void init_rows(Domain& d, int r_begin, int r_end, uint64_t seed, uint64_t run,
                      const double p_init[N_STRAINS]) {
    for (int r = r_begin; r < r_end; ++r) {
        const int grow = d.row_offset + r;
        for (int s = 0; s < N_STRAINS; ++s) {
            Rng rng(stream_seed(seed, run, INIT_TAG, 0, s, grow));
            StrainBoards& b = d.cur[s];
            const double p_mosq_inf = std::min(1.0, p_init[s] * 2.0);
            for (int c = 0; c < d.L; ++c) {  // humanos
                const size_t i = d.idx(r, c);
                const int inf = sample_binomial(rng, AC_CELL_POPULATION, p_init[s]);
                b.Ih[i] = inf; b.Rh[i] = 0; b.Sh[i] = AC_CELL_POPULATION - inf;
            }
            for (int c = 0; c < d.L; ++c) {  // mosquitos (25 % de K_M)
                const size_t i = d.idx(r, c);
                const int init_m = sample_binomial(rng, AC_MAX_MOSQUITOES_PER_CELL, 0.25);
                const int inf_m = sample_binomial(rng, init_m, p_mosq_inf);
                b.Im[i] = inf_m; b.Sm[i] = init_m - inf_m;
            }
        }
    }
}

// Rellena las filas fantasma de forma periódica cuando el dominio local es el
// tablero completo (serial y OpenMP). Solo hacen falta I_h, I_m y S_m (S_m+I_m
// = mosquitos vivos), que son los tableros cuya suma de vecinos se usa.
inline void fill_ghosts_local(Domain& d) {
    const size_t L = d.L;
    for (int s = 0; s < N_STRAINS; ++s) {
        for (Board* b : {&d.cur[s].Ih, &d.cur[s].Im, &d.cur[s].Sm}) {
            std::copy(b->begin() + d.rows * L, b->begin() + (d.rows + 1) * L, b->begin());           // fila L-1 -> fantasma superior
            std::copy(b->begin() + L, b->begin() + 2 * L, b->begin() + (d.rows + 1) * L);              // fila 0   -> fantasma inferior
        }
    }
}

// =============================================================================
// 5. REGLA DE EVOLUCIÓN DE UNA FILA (ac_step_strain_day de utils_pure.py)
// =============================================================================
// Lee de d.cur[strain] (con fantasmas válidos) y escribe en d.nxt[strain]
// (doble buffer: ninguna celda lee un valor ya actualizado). Devuelve los casos
// nuevos de la fila (infecciones nuevas + recaídas). Seguro para hilos: cada
// fila escribe solo en su propia fila de nxt y usa su propio generador.
inline int64_t step_row(Domain& d, int strain, int r, const StepConstants& k, Rng& rng) {
    const StrainBoards& b = d.cur[strain];
    StrainBoards& n = d.nxt[strain];
    const int L = d.L;
    const int32_t* ih_u = &b.Ih[d.idx(r - 1, 0)]; const int32_t* ih_c = &b.Ih[d.idx(r, 0)]; const int32_t* ih_d = &b.Ih[d.idx(r + 1, 0)];
    const int32_t* im_u = &b.Im[d.idx(r - 1, 0)]; const int32_t* im_c = &b.Im[d.idx(r, 0)]; const int32_t* im_d = &b.Im[d.idx(r + 1, 0)];
    const int32_t* sm_u = &b.Sm[d.idx(r - 1, 0)]; const int32_t* sm_c = &b.Sm[d.idx(r, 0)]; const int32_t* sm_d = &b.Sm[d.idx(r + 1, 0)];
    int64_t cases = 0;

    for (int c = 0; c < L; ++c) {
        const int cp = d.c_prev[c], cn = d.c_next[c];
        const size_t i = d.idx(r, c);

        // Suma de los 8 vecinos de Moore (toroide)
        const int ih_neigh = ih_u[cp] + ih_u[c] + ih_u[cn] + ih_c[cp] + ih_c[cn] + ih_d[cp] + ih_d[c] + ih_d[cn];
        const int im_neigh = im_u[cp] + im_u[c] + im_u[cn] + im_c[cp] + im_c[cn] + im_d[cp] + im_d[c] + im_d[cn];
        const int sm_neigh = sm_u[cp] + sm_u[c] + sm_u[cn] + sm_c[cp] + sm_c[cn] + sm_d[cp] + sm_d[c] + sm_d[cn];
        const int m_alive_neigh = sm_neigh + im_neigh;

        const int s_h = b.Sh[i], i_h = b.Ih[i], r_h = b.Rh[i];
        const int s_m = b.Sm[i], i_m = b.Im[i];

        const double i_m_eff = calc_effective_exposure(i_m, im_neigh / 8.0);
        const double i_h_eff = calc_effective_exposure(i_h, ih_neigh / 8.0);

        // Dinámica humana S -> I -> R -> S (con recaídas en P. vivax)
        const double p_infect_h = calc_infection_probability(k.rate_m_to_h, i_m_eff, k.dt);
        const int new_infected_h  = sample_binomial(rng, s_h, p_infect_h);
        const int new_recovered_h = sample_binomial(rng, i_h, k.p_recover_h);
        const int relapsed_h      = k.has_relapse ? sample_binomial(rng, r_h, k.p_relapse) : 0;
        const int remaining_r_h   = std::max(0, r_h - relapsed_h);
        const int lost_immunity_h = sample_binomial(rng, remaining_r_h, k.p_loss_imm_h);

        n.Sh[i] = s_h - new_infected_h + lost_immunity_h;
        n.Ih[i] = i_h + new_infected_h - new_recovered_h + relapsed_h;
        n.Rh[i] = remaining_r_h + new_recovered_h - lost_immunity_h;
        cases += new_infected_h + relapsed_h;

        // Dinámica del mosquito: nacimiento -> S_m -> I_m -> muerte
        const int dead_s_m = sample_binomial(rng, s_m, k.p_death_m);
        const int dead_i_m = sample_binomial(rng, i_m, k.p_death_m);
        const int s_m_surv = s_m - dead_s_m;
        const int i_m_surv = i_m - dead_i_m;

        const int empty_slots = std::max(0, AC_MAX_MOSQUITOES_PER_CELL - (s_m_surv + i_m_surv));
        const double p_birth = clip01(
            AC_MOSQUITO_WEATHER_DENSITY * k.climate_suitability * k.dt +
            AC_MOSQUITO_NEIGHBORS_DENSITY * ((m_alive_neigh / 8.0) / AC_MAX_MOSQUITOES_PER_CELL) * k.dt);
        const int newborn_m = sample_binomial(rng, empty_slots, p_birth);

        const double p_infect_m = calc_infection_probability(k.rate_h_to_m, i_h_eff, k.dt);
        const int new_infected_m = sample_binomial(rng, s_m_surv, p_infect_m);

        n.Sm[i] = s_m_surv - new_infected_m + newborn_m;
        n.Im[i] = i_m_surv + new_infected_m;
    }
    return cases;
}

// Totales de una fila para las métricas mensuales:
// [S_h, I_h, R_h, S_m, I_m] por cepa -> 10 valores (falciparum primero).
constexpr int N_TOTALS = 10;
inline void accumulate_row_totals(const Domain& d, int r, int64_t tot[N_TOTALS]) {
    for (int s = 0; s < N_STRAINS; ++s) {
        const StrainBoards& b = d.cur[s];
        int64_t sh = 0, ih = 0, rh = 0, sm = 0, im = 0;
        for (int c = 0; c < d.L; ++c) {
            const size_t i = d.idx(r, c);
            sh += b.Sh[i]; ih += b.Ih[i]; rh += b.Rh[i]; sm += b.Sm[i]; im += b.Im[i];
        }
        tot[s * 5 + 0] += sh; tot[s * 5 + 1] += ih; tot[s * 5 + 2] += rh;
        tot[s * 5 + 3] += sm; tot[s * 5 + 4] += im;
    }
}

// =============================================================================
// 6. DATOS DE ENTRADA Y SALIDAS
// =============================================================================
struct MonthRow {
    std::string fecha;  // YYYY-MM-DD
    double poblacion_total, temperatura, humedad, precipitacion;
    double ipa_falciparum, ipa_vivax;
    int dias_mes;
};

struct RegionData {
    std::string name;   // como en el dataset (p. ej. "Pacifico")
    std::string lower;  // en minúsculas (p. ej. "pacifico")
    std::vector<MonthRow> months;  // ordenados por fecha
    int L = 0;
    double p_init[N_STRAINS] = {0.0, 0.0};
};

inline std::string to_lower(std::string s) {
    for (char& ch : s) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return s;
}

// Lee data/GAM_regional_enriquecido.csv (generado por tools/export_csv.py).
// board_size_override > 0 fuerza el lado L del tablero (clima e IPA inicial de
// la región no cambian). Es SOLO para el experimento de escalabilidad débil
// (guía §6.6, G6); las corridas normales usan el L de la población (AGENTS.md §2.1).
inline std::map<std::string, RegionData> load_regions(const std::string& path, int board_size_override = 0) {
    std::ifstream in(path);
    if (!in) {
        std::cerr << "ERROR: no se pudo abrir " << path
                  << " (genérelo con: python tools/export_csv.py)\n";
        std::exit(1);
    }
    std::string line;
    std::getline(in, line);  // encabezado
    std::map<std::string, RegionData> regions;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::vector<std::string> f;
        std::stringstream ss(line);
        std::string tok;
        while (std::getline(ss, tok, ',')) f.push_back(tok);
        if (f.size() < 11) { std::cerr << "ERROR: línea mal formada en " << path << "\n"; std::exit(1); }
        MonthRow m;
        m.fecha = f[1];
        m.poblacion_total = std::stod(f[2]);
        m.temperatura = std::stod(f[3]);
        m.humedad = std::stod(f[4]);
        m.precipitacion = std::stod(f[5]);
        m.ipa_falciparum = std::stod(f[6]);
        m.ipa_vivax = std::stod(f[7]);
        m.dias_mes = std::stoi(f[10]);
        RegionData& rd = regions[to_lower(f[0])];
        rd.name = f[0];
        rd.lower = to_lower(f[0]);
        rd.months.push_back(m);
    }
    for (auto& [key, rd] : regions) {
        std::sort(rd.months.begin(), rd.months.end(),
                  [](const MonthRow& a, const MonthRow& b) { return a.fecha < b.fecha; });
        const MonthRow& first = rd.months.front();
        rd.L = board_size_override > 0 ? board_size_override : board_size_from_population(first.poblacion_total);
        rd.p_init[FALCIPARUM] = clip01(first.ipa_falciparum / AC_CELL_POPULATION);
        rd.p_init[VIVAX] = clip01(first.ipa_vivax / AC_CELL_POPULATION);
    }
    return regions;
}

// Fila mensual de métricas (12 valores enteros: 10 totales + 2 casos).
struct MonthMetrics {
    int64_t totals[N_TOTALS];
    int64_t cases[N_STRAINS];
};

inline bool file_exists(const std::string& p) { struct stat st; return stat(p.c_str(), &st) == 0; }
inline void make_dir(const std::string& p) { mkdir(p.c_str(), 0755); }

inline double unix_timestamp() {
    return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
}

// outputs/times.csv en modo append; encabezado si no existe (AGENTS.md §8).
inline void append_times(const std::string& outdir, const std::string& paradigm, const std::string& region,
                         int workers, int L, double elapsed) {
    make_dir(outdir);
    const std::string path = outdir + "/times.csv";
    const bool exists = file_exists(path);
    FILE* fp = std::fopen(path.c_str(), "a");
    if (!fp) { std::cerr << "ERROR: no se pudo abrir " << path << "\n"; std::exit(1); }
    if (!exists)
        std::fprintf(fp, "execution_timestamp,language,paradigm,region,workers,board_size,iterations,elapsed_time\n");
    std::fprintf(fp, "%.6f,cpp,%s,%s,%d,%d,%d,%.9f\n", unix_timestamp(), paradigm.c_str(), region.c_str(),
                 workers, L, ITERATIONS, elapsed);
    std::fclose(fp);
}

// outputs/metrics/{paradigm}_{region}[_run{id}].csv con las 18 columnas de AGENTS.md §9.1.
inline void write_metrics(const std::string& outdir, const std::string& paradigm, const RegionData& rd,
                          const std::vector<MonthMetrics>& hist, int run, int total_runs) {
    make_dir(outdir);
    make_dir(outdir + "/metrics");
    std::string path = outdir + "/metrics/" + paradigm + "_" + rd.lower;
    if (total_runs > 1) path += "_run" + std::to_string(run);
    path += ".csv";
    FILE* fp = std::fopen(path.c_str(), "w");
    if (!fp) { std::cerr << "ERROR: no se pudo escribir " << path << "\n"; std::exit(1); }
    std::fprintf(fp,
        "paradigm,region,fecha,"
        "falciparum_S_h,falciparum_I_h,falciparum_R_h,falciparum_S_m,falciparum_I_m,"
        "falciparum_nuevos_casos_mes,IPA_falciparum_simulado,IPA_falciparum_real,"
        "vivax_S_h,vivax_I_h,vivax_R_h,vivax_S_m,vivax_I_m,"
        "vivax_nuevos_casos_mes,IPA_vivax_simulado,IPA_vivax_real\n");
    const double cells = static_cast<double>(rd.L) * rd.L;
    for (size_t t = 0; t < hist.size(); ++t) {
        const MonthMetrics& m = hist[t];
        const MonthRow& row = rd.months[t];
        std::fprintf(fp, "%s,%s,%s", paradigm.c_str(), rd.lower.c_str(), row.fecha.c_str());
        for (int s = 0; s < N_STRAINS; ++s) {
            const int64_t* tt = &m.totals[s * 5];
            const double ipa_real = (s == FALCIPARUM) ? row.ipa_falciparum : row.ipa_vivax;
            std::fprintf(fp, ",%lld,%lld,%lld,%lld,%lld,%lld,%.17g,%.17g",
                         (long long)tt[0], (long long)tt[1], (long long)tt[2], (long long)tt[3], (long long)tt[4],
                         (long long)m.cases[s], m.cases[s] / cells, ipa_real);
        }
        std::fprintf(fp, "\n");
    }
    std::fclose(fp);
}

// Paso de tiempo de un mes: dt = días_del_mes / 4.
inline double month_dt(const MonthRow& m) { return m.dias_mes / static_cast<double>(AC_STEPS_PER_MONTH); }

// =============================================================================
// 7. ARGUMENTOS COMUNES
// =============================================================================
struct Args {
    std::string region = "pacifico";
    int runs = 1;
    uint64_t seed = 12345;
    bool metrics = true;
    int warmup = 1;   // ejecuciones de calentamiento no registradas (guía §6.4)
    int threads = 0;  // solo OpenMP (0 = usar OMP_NUM_THREADS)
    std::string schedule = "static";  // solo OpenMP
    int board_size = 0;  // SOLO experimentos de escalabilidad débil (0 = L de la región)
    std::string data = "../data/GAM_regional_enriquecido.csv";
    std::string outdir = "../outputs";
};

inline void print_usage(const char* prog, bool openmp) {
    std::fprintf(stderr,
        "Uso: %s [--region {amazonia|andina|caribe|orinoquia|pacifico|todo}] [--runs N] [--seed S]\n"
        "          [--no-metrics] [--warmup W] [--data RUTA_CSV] [--outdir CARPETA] [--board-size L]%s\n",
        prog, openmp ? "\n          [--threads N] [--schedule {static|dynamic|guided}]" : "");
}

inline Args parse_args(int argc, char** argv, bool openmp, bool quiet = false) {
    Args a;
    auto need = [&](int& i) -> std::string {
        if (i + 1 >= argc) { if (!quiet) print_usage(argv[0], openmp); std::exit(2); }
        return argv[++i];
    };
    for (int i = 1; i < argc; ++i) {
        const std::string s = argv[i];
        if (s == "--region") a.region = to_lower(need(i));
        else if (s == "--runs") a.runs = std::stoi(need(i));
        else if (s == "--seed") a.seed = std::stoull(need(i));
        else if (s == "--no-metrics") a.metrics = false;
        else if (s == "--warmup") a.warmup = std::stoi(need(i));
        else if (s == "--data") a.data = need(i);
        else if (s == "--outdir") a.outdir = need(i);
        else if (s == "--board-size") a.board_size = std::stoi(need(i));
        else if (openmp && s == "--threads") a.threads = std::stoi(need(i));
        else if (openmp && s == "--schedule") a.schedule = to_lower(need(i));
        else if (s == "-h" || s == "--help") { if (!quiet) print_usage(argv[0], openmp); std::exit(0); }
        else { if (!quiet) { std::fprintf(stderr, "Argumento desconocido: %s\n", s.c_str()); print_usage(argv[0], openmp); } std::exit(2); }
    }
    static const char* valid[] = {"amazonia", "andina", "caribe", "orinoquia", "pacifico", "todo"};
    if (std::find(std::begin(valid), std::end(valid), a.region) == std::end(valid)) {
        if (!quiet) { std::fprintf(stderr, "Región inválida: %s\n", a.region.c_str()); print_usage(argv[0], openmp); }
        std::exit(2);
    }
    if (a.runs < 1 || a.warmup < 0) { if (!quiet) print_usage(argv[0], openmp); std::exit(2); }
    return a;
}

// Regiones a ejecutar, en orden alfabético.
inline std::vector<const RegionData*> select_regions(const std::map<std::string, RegionData>& all,
                                                     const std::string& region) {
    std::vector<const RegionData*> out;
    for (const auto& [key, rd] : all)
        if (region == "todo" || key == region) out.push_back(&rd);
    if (out.empty()) { std::cerr << "ERROR: región no encontrada en el CSV: " << region << "\n"; std::exit(1); }
    for (const RegionData* rd : out)
        if (static_cast<int>(rd->months.size()) != ITERATIONS) {
            std::cerr << "ERROR: " << rd->name << " tiene " << rd->months.size() << " meses (se esperaban 204)\n";
            std::exit(1);
        }
    return out;
}

}  // namespace hpc
