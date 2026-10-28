// Grid A* for a 2-layer board. State = (layer, y, x, dir): dir 0..7 = last step,
// 8 = arrived through a via (no second via straight after), 9 = start.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int32_t f; int32_t s; } Item;
static Item *heap; static int hn, hcap;
static void push(int32_t f, int32_t s) {
    if (hn == hcap) { hcap = hcap ? hcap * 2 : 1 << 16; heap = realloc(heap, hcap * sizeof(Item)); }
    int i = hn++;
    while (i) { int p = (i - 1) / 2; if (heap[p].f <= f) break; heap[i] = heap[p]; i = p; }
    heap[i].f = f; heap[i].s = s;
}
static Item pop(void) {
    Item top = heap[0], last = heap[--hn]; int i = 0;
    for (;;) { int c = 2 * i + 1; if (c >= hn) break;
        if (c + 1 < hn && heap[c + 1].f < heap[c].f) c++;
        if (heap[c].f >= last.f) break; heap[i] = heap[c]; i = c; }
    heap[i] = last; return top;
}
static const int DX[8] = {1, 1, 0, -1, -1, -1, 0, 1};
static const int DY[8] = {0, 1, 1, 1, 0, -1, -1, -1};

// blockT: [2][H][W]; blockV: [H][W]; src/tgt: [2][H][W]; cost: [2][H][W] extra cost per cell;
// costV: [H][W] extra cost per via.
// Returns path length (cells) written into out as (layer*H + y)*W + x, from target back to source.
int route(int W, int H, const uint8_t *blockT, const uint8_t *blockV, const uint8_t *src,
          const uint8_t *tgt, const uint16_t *cost, const uint16_t *costV, int step, int diag, int via, int turn,
          int tx0, int ty0, int tx1, int ty1, int32_t *out, int maxout) {
    long N = 2L * H * W; long S = N * 10;
    int32_t *g = malloc(S * sizeof(int32_t));
    int32_t *par = malloc(S * sizeof(int32_t));
    if (!g || !par) return -2;
    for (long i = 0; i < S; i++) g[i] = INT32_MAX;
    hn = 0;
    // heuristic: distance to target bbox
    #define HEUR(x, y) ({ int ddx = (x) < tx0 ? tx0 - (x) : ((x) > tx1 ? (x) - tx1 : 0); \
        int ddy = (y) < ty0 ? ty0 - (y) : ((y) > ty1 ? (y) - ty1 : 0); \
        int mn = ddx < ddy ? ddx : ddy, mx = ddx < ddy ? ddy : ddx; mn * diag + (mx - mn) * step; })
    for (long c = 0; c < N; c++) if (src[c] && !blockT[c]) {
        long s = c * 10 + 9; g[s] = 0; par[s] = -1;
        int x = c % W, y = (c / W) % H; push(HEUR(x, y), (int32_t)s);
    }
    long found = -1;
    while (hn) {
        Item it = pop(); long s = it.s; long c = s / 10; int d = s % 10;
        int x = c % W, y = (c / W) % H, l = c / ((long)W * H);
        int gs = g[s]; if (it.f - HEUR(x, y) > gs) continue;
        if (tgt[c]) { found = s; break; }
        for (int nd = 0; nd < 8; nd++) {
            int nx = x + DX[nd], ny = y + DY[nd];
            if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
            long nc = ((long)l * H + ny) * W + nx;
            if (blockT[nc]) continue;
            if (nd & 1) { // diagonal: both orthogonal neighbours must be free
                if (blockT[((long)l * H + y) * W + nx] || blockT[((long)l * H + ny) * W + x]) continue;
            }
            int t = 0;
            if (d < 8) { int dd = abs(nd - d); if (dd > 4) dd = 8 - dd; if (dd > 2) continue; t = dd * turn; }
            int ng = gs + ((nd & 1) ? diag : step) + t + cost[nc];
            long ns = nc * 10 + nd;
            if (ng < g[ns]) { g[ns] = ng; par[ns] = (int32_t)s; push(ng + HEUR(nx, ny), (int32_t)ns); }
        }
        // via
        if (d != 8 && !blockV[(long)y * W + x]) {
            long nc = ((long)(1 - l) * H + y) * W + x;
            if (!blockT[nc]) {
                int ng = gs + via + cost[nc] + costV[(long)y * W + x]; long ns = nc * 10 + 8;
                if (ng < g[ns]) { g[ns] = ng; par[ns] = (int32_t)s; push(ng + HEUR(x, y), (int32_t)ns); }
            }
        }
    }
    int n = 0;
    if (found >= 0) {
        for (long s = found; s >= 0 && n < maxout; s = par[s]) out[n++] = (int32_t)(s / 10);
    } else n = -1;
    free(g); free(par);
    return n;
}
