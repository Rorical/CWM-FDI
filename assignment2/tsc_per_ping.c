#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <x86intrin.h>

static inline uint64_t read_tsc(void) {
    _mm_lfence();
    uint64_t t = __rdtsc();
    _mm_lfence();
    return t;
}

int main() {
    uint64_t tsc_start = read_tsc();
    int ret = system("ping 8.8.8.8 -c 1 -W 2 > /dev/null 2>&1");
    uint64_t tsc_end = read_tsc();
    if (ret != 0) {
        printf("ping failed, trying google.com...\n");
        tsc_start = read_tsc();
        ret = system("ping google.com -c 1 -W 2 > /dev/null 2>&1");
        tsc_end = read_tsc();
    }
    uint64_t cycles = tsc_end - tsc_start;
    // Time per TSC read is about 55 cycles (from Q5)
    uint64_t tsc_reads = cycles / 55;
    printf("Total TSC cycles for one ping RTT: %llu\n", (unsigned long long)cycles);
    printf("Estimated TSC reads per ping RTT: %llu\n", (unsigned long long)tsc_reads);
    return 0;
}
