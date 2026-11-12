/* Four threads call a function that keeps state, with and without a fix. Build and run under ThreadSanitizer:
 *   cc -g -O1 -fsanitize=thread -o tsan_demo tsan_demo.c fw_describe.c -lpthread
 *   ./tsan_demo static | caller | counter | atomic | mutex
 */
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

const char *fw_describe_static(unsigned id, unsigned mv);
int fw_describe(char *out, size_t cap, unsigned id, unsigned mv);

#define THREADS 4
#define CALLS 2000

static int plain_counter;
static atomic_int atomic_counter;
static int locked_counter;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static const char *mode;

static void *work(void *arg)
{
    unsigned t = (unsigned)(size_t)arg;
    for (int i = 0; i < CALLS; i++) {
        if (strcmp(mode, "static") == 0) {
            const char *s = fw_describe_static(10 + t, 3300 + t);   /* reads the shared buffer */
            (void)s[0];
        } else if (strcmp(mode, "caller") == 0) {
            char out[48];
            fw_describe(out, sizeof out, 10 + t, 3300 + t);
        } else if (strcmp(mode, "counter") == 0) {
            plain_counter++;
        } else if (strcmp(mode, "atomic") == 0) {
            atomic_fetch_add(&atomic_counter, 1);
        } else {
            pthread_mutex_lock(&lock);
            locked_counter++;
            pthread_mutex_unlock(&lock);
        }
    }
    return NULL;
}

int main(int argc, char **argv)
{
    mode = argc > 1 ? argv[1] : "static";
    pthread_t th[THREADS];
    for (size_t t = 0; t < THREADS; t++) {
        pthread_create(&th[t], NULL, work, (void *)t);
    }
    for (int t = 0; t < THREADS; t++) {
        pthread_join(th[t], NULL);
    }
    printf("%s: done\n", mode);
    return 0;
}
