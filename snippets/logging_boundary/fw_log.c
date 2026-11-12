/* A firmware-style library that reports through a log callback and, for comparison, through stdio. */
#include <pthread.h>
#include <stdio.h>

typedef void (*fw_log_fn)(int level, const char *msg);

static fw_log_fn g_log;

void fw_log_set(fw_log_fn fn) { g_log = fn; }

static void emit(int level, const char *msg)
{
    if (g_log != NULL) {
        g_log(level, msg);
    }
}

/* Reports through the callback: 10 debug, 20 info, 30 warning, 40 error (the Python logging levels). */
void fw_selftest(void)
{
    emit(20, "selftest start");
    emit(30, "sensor 2 reads 3.31 V, limit 3.30 V");
    emit(40, "sensor 3 not responding");
}

/* Reports through stdio, as an older firmware library would. */
void fw_printf_line(int n)
{
    printf("C line %d\n", n);
}

void fw_printf_flush(void)
{
    fflush(stdout);
}

static void *worker(void *arg)
{
    (void)arg;
    emit(20, "message from a thread that Python did not create");
    return NULL;
}

/* Calls the callback from a thread created in C and waits for it. */
void fw_selftest_thread(void)
{
    pthread_t t;
    if (pthread_create(&t, NULL, worker, NULL) == 0) {
        pthread_join(t, NULL);
    }
}
