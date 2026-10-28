/* The newlib system calls the C library references, so the image does not depend on libnosys: no files, no console,
 * a heap between the end of .bss and the stack's reserve (the firmware itself never allocates). */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>

extern uint8_t end;            /* the linker script: the end of .bss */
extern uint8_t _estack;
extern uint32_t _Min_Stack_Size;

void *_sbrk(ptrdiff_t incr)
{
    static uint8_t *brk = &end;
    const uint8_t *limit = &_estack - (uint32_t)&_Min_Stack_Size;
    if (brk + incr > limit) {
        errno = ENOMEM;
        return (void *)-1;
    }
    uint8_t *prev = brk;
    brk += incr;
    return prev;
}

void _exit(int status)
{
    (void)status;
    for (;;) {
    }
}

int _kill(int pid, int sig) { (void)pid; (void)sig; errno = EINVAL; return -1; }
int _getpid(void) { return 1; }
int _close(int fd) { (void)fd; errno = EBADF; return -1; }
int _lseek(int fd, int off, int dir) { (void)fd; (void)off; (void)dir; return 0; }
int _read(int fd, char *p, int n) { (void)fd; (void)p; (void)n; return 0; }
int _write(int fd, const char *p, int n) { (void)fd; (void)p; return n; }
int _fstat(int fd, struct stat *st) { (void)fd; st->st_mode = S_IFCHR; return 0; }
int _isatty(int fd) { (void)fd; return 1; }
