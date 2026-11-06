/* VectorNav VN-100 binary packets (group 1: YawPitchRoll + AngularRate) and ASCII commands. */
#include "gp/gp_vn100.h"

#include <string.h>

static const uint8_t HEAD[4] = {GP_VN100_SYNC, 0x01u, 0x28u, 0x00u};

void gp_vn100_init(gp_vn100_parser *p)
{
    memset(p, 0, sizeof *p);
}

uint16_t gp_vn100_crc(const uint8_t *d, size_t n)
{
    uint16_t crc = 0;
    for (size_t i = 0; i < n; i++) { /* VectorNav's calculateCRC: CRC-16-CCITT, poly 0x1021, init 0 */
        crc = (uint16_t)((uint8_t)(crc >> 8) | (uint16_t)(crc << 8));
        crc ^= d[i];
        crc ^= (uint16_t)((uint8_t)(crc & 0xFFu) >> 4);
        crc ^= (uint16_t)(crc << 12);
        crc ^= (uint16_t)((crc & 0x00FFu) << 5);
    }
    return crc;
}

static float rdf(const uint8_t *d)
{
    uint32_t u = (uint32_t)d[0] | ((uint32_t)d[1] << 8) | ((uint32_t)d[2] << 16) | ((uint32_t)d[3] << 24);
    float f;
    memcpy(&f, &u, 4);
    return f;
}

static void wrf(uint8_t *d, float f)
{
    uint32_t u;
    memcpy(&u, &f, 4);
    for (int k = 0; k < 4; k++) {
        d[k] = (uint8_t)(u >> (8 * k));
    }
}

/* Drop the buffer's first byte and look for the next sync byte in what is left. */
static void resync(gp_vn100_parser *p)
{
    p->resyncs++;
    uint8_t k = 1;
    while (k < p->n && p->buf[k] != GP_VN100_SYNC) {
        k++;
    }
    memmove(p->buf, p->buf + k, (size_t)(p->n - k));
    p->n = (uint8_t)(p->n - k);
}

int gp_vn100_feed(gp_vn100_parser *p, const uint8_t *data, size_t n, gp_vn100_sample *out)
{
    int good = 0;
    for (size_t i = 0; i < n; i++) {
        if (p->n == 0 && data[i] != GP_VN100_SYNC) {
            continue; /* hunting for a sync byte (ASCII replies and noise pass by here) */
        }
        p->buf[p->n++] = data[i];
        for (;;) {
            /* the header so far must match */
            uint8_t h = p->n < 4 ? p->n : 4;
            if (memcmp(p->buf, HEAD, h) != 0) {
                resync(p);
                if (p->n == 0) break;
                continue;
            }
            if (p->n < GP_VN100_PACKET) break;
            if (gp_vn100_crc(p->buf + 1, GP_VN100_PACKET - 1) != 0) {
                p->crc_errors++;
                resync(p);
                if (p->n == 0) break;
                continue;
            }
            const uint8_t *b = p->buf + 4;
            out->yaw = rdf(b);
            out->pitch = rdf(b + 4);
            out->roll = rdf(b + 8);
            out->gx = rdf(b + 12);
            out->gy = rdf(b + 16);
            out->gz = rdf(b + 20);
            p->packets++;
            good++;
            p->n = 0;
            break;
        }
    }
    return good;
}

size_t gp_vn100_encode(const gp_vn100_sample *s, uint8_t out[GP_VN100_PACKET])
{
    memcpy(out, HEAD, 4);
    wrf(out + 4, s->yaw);
    wrf(out + 8, s->pitch);
    wrf(out + 12, s->roll);
    wrf(out + 16, s->gx);
    wrf(out + 20, s->gy);
    wrf(out + 24, s->gz);
    const uint16_t crc = gp_vn100_crc(out + 1, GP_VN100_PACKET - 3);
    out[28] = (uint8_t)(crc >> 8);
    out[29] = (uint8_t)crc;
    return GP_VN100_PACKET;
}

size_t gp_vn100_command(const char *body, char *out, size_t cap)
{
    static const char hex[] = "0123456789ABCDEF";
    const size_t n = strlen(body);
    if (cap < n + 7) {
        return 0;
    }
    uint8_t x = 0;
    out[0] = '$';
    for (size_t i = 0; i < n; i++) {
        out[1 + i] = body[i];
        x ^= (uint8_t)body[i];
    }
    out[n + 1] = '*';
    out[n + 2] = hex[x >> 4];
    out[n + 3] = hex[x & 0xFu];
    out[n + 4] = '\r';
    out[n + 5] = '\n';
    out[n + 6] = '\0';
    return n + 6;
}
