// Prueba de exactitud de std::binomial_distribution (libstdc++) frente a la media teórica n*p.
// Explica la pequeña discrepancia estadística C++ vs Python puro (ver informe).
// Compilar: g++ -O3 -std=c++17 tools/binomial_bias_test.cpp -o /tmp/bintest && /tmp/bintest  (~1 min)
#include <random>
#include <cstdio>
#include <cmath>
int main(){
  std::mt19937_64 g(7);
  struct C{int n; double p;} cs[]={{1000,0.03},{1000,0.005},{1000,0.36}};
  for(auto c:cs){ const long M=40000000; double s=0;
    for(long i=0;i<M;i++){ std::binomial_distribution<int> d(c.n,c.p); s+=d(g);}
    double mu=c.n*c.p, se=std::sqrt(c.n*c.p*(1-c.p)/M), mean=s/M;
    printf("n=%d p=%.3f np=%.1f media=%.5f teorica=%.5f sesgo_rel=%.2e z=%.1f\n",c.n,c.p,mu,mean,mu,(mean-mu)/mu,(mean-mu)/se);}
}
