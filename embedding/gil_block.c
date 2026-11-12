/* Why the thread that starts the interpreter must call PyEval_SaveThread().
 * Usage: gil_block save | nosave
 * "nosave" waits for ever by design: run it under timeout(1). */
#include <Python.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>

static void *worker_main(void *arg)
{
    (void)arg;
    puts("worker: calling PyGILState_Ensure()");
    PyGILState_STATE gil = PyGILState_Ensure();
    puts("worker: holds the GIL");
    PyRun_SimpleString("print('worker: Python says', 6 * 7, flush=True)");
    PyGILState_Release(gil);
    return NULL;
}

int main(int argc, char **argv)
{
    int save = argc == 2 && strcmp(argv[1], "save") == 0;
    if (!save && !(argc == 2 && strcmp(argv[1], "nosave") == 0)) {
        fprintf(stderr, "usage: %s save|nosave\n", argv[0]);
        return 2;
    }
    setvbuf(stdout, NULL, _IOLBF, 0);  /* every line shows even if the run is killed */

    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    PyStatus status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        fprintf(stderr, "start-up failed: %s\n", status.err_msg ? status.err_msg : "?");
        return 2;
    }

    /* Py_InitializeFromConfig() returns with the GIL held by this thread */
    PyThreadState *saved = save ? PyEval_SaveThread() : NULL;
    printf("main: GIL %s, starting the worker\n", saved ? "released" : "still held");
    pthread_t worker;
    pthread_create(&worker, NULL, worker_main, NULL);
    puts("main: waiting in pthread_join()");
    pthread_join(worker, NULL);
    puts("main: worker finished");
    if (saved) {
        PyEval_RestoreThread(saved);
    }
    return Py_FinalizeEx() < 0;
}
