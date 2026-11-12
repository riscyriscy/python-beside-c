/* A C program that embeds the Python interpreter: it owns main(), exposes the
 * firmware's crc16_ccitt() to scripts as the module "fw", and calls rules written
 * in limits.py. The interpreter starts in isolated mode, and a second thread calls
 * into it.
 * Usage: sequencer <directory that holds limits.py> */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pthread.h>
#include <stdio.h>

#include "crc16.h"

/* fw.crc16(data) -> int, the same C function the firmware runs */
static PyObject *fw_crc16(PyObject *self, PyObject *arg)
{
    (void)self;
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) < 0) {
        return NULL;
    }
    unsigned long crc = crc16_ccitt((const uint8_t *)view.buf, (size_t)view.len);
    PyBuffer_Release(&view);
    return PyLong_FromUnsignedLong(crc);
}

static PyMethodDef fw_methods[] = {
    {"crc16", fw_crc16, METH_O, "CRC-16/CCITT-FALSE of a bytes-like object."},
    {NULL, NULL, 0, NULL},
};
static struct PyModuleDef fw_def = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "fw",
    .m_size = -1,
    .m_methods = fw_methods,
};
static PyObject *init_fw(void) { return PyModule_Create(&fw_def); }

/* Print and clear the pending Python exception.
 * Returns -1 so callers can "return report()". */
static int report(const char *where)
{
    PyObject *exc = PyErr_GetRaisedException();
    PyObject *text = exc ? PyObject_Str(exc) : NULL;
    printf("%s: %s: %s\n", where, exc ? Py_TYPE(exc)->tp_name : "(no exception)",
           text ? PyUnicode_AsUTF8(text) : "?");
    Py_XDECREF(text);
    Py_XDECREF(exc);
    PyErr_Clear();  /* in case formatting the message failed too */
    return -1;
}

/* Each helper returns 0 for pass, 1 for a failed check and -1 when the call raised. */
static int check(PyObject *check_fn, const char *name, double value)
{
    /* the result is a new reference */
    PyObject *result = PyObject_CallFunction(check_fn, "sd", name, value);
    if (result == NULL) {
        return report(name);
    }
    int ok = 0;
    const char *message = NULL;
    /* message is valid while result lives */
    if (!PyArg_ParseTuple(result, "ps", &ok, &message)) {
        Py_DECREF(result);
        return report(name);
    }
    printf("%s  %s\n", ok ? "PASS" : "FAIL", message);
    Py_DECREF(result);
    return ok ? 0 : 1;
}

static int frame_ok(PyObject *frame_ok_fn, const char *label, const uint8_t *frame,
                    size_t len)
{
    PyObject *result =
        PyObject_CallFunction(frame_ok_fn, "y#", (const char *)frame, (Py_ssize_t)len);
    if (result == NULL) {
        return report("frame_ok");
    }
    int ok = PyObject_IsTrue(result);
    Py_DECREF(result);
    printf("%s  %s, %zu bytes\n", ok ? "PASS" : "FAIL", label, len);
    return ok ? 0 : 1;
}

/* Start the interpreter in isolated mode: PYTHONHOME, PYTHONPATH, the other PYTHON*
 * variables, the user site directory and the command line cannot change what it
 * imports. Returns 0, or -1 after printing the reason. */
static int start_interpreter(void)
{
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    PyStatus status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);  /* the interpreter keeps its own copy */
    if (PyStatus_Exception(status)) {
        fprintf(stderr, "Python start-up failed: %s%s%s\n",
                status.func ? status.func : "", status.func ? ": " : "",
                status.err_msg ? status.err_msg : "(no message)");
        return -1;
    }
    return 0;
}

/* A worker thread that the interpreter did not create. PyGILState_Ensure() attaches
 * it to the interpreter and takes the global interpreter lock (GIL), which the main
 * thread must have released first. */
struct worker_job {
    PyObject *check_fn;
    int not_passed;
};

static void *worker_main(void *arg)
{
    struct worker_job *job = arg;
    PyGILState_STATE gil = PyGILState_Ensure();
    printf("worker thread: ");
    job->not_passed = check(job->check_fn, "rate_hz", 10) != 0;
    PyGILState_Release(gil);
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <directory with limits.py>\n", argv[0]);
        return 2;
    }
    /* must come before the interpreter starts */
    if (PyImport_AppendInittab("fw", init_fw) < 0) {
        return 2;
    }
    if (start_interpreter() < 0) {
        return 2;
    }

    int not_passed = 0;  /* failed checks plus calls that raised */
    PyObject *path = PySys_GetObject("path");  /* borrowed reference */
    PyObject *dir = PyUnicode_FromString(argv[1]);
    if (path == NULL || dir == NULL || PyList_Insert(path, 0, dir) < 0) {
        report("sys.path");
        return 2;
    }
    Py_DECREF(dir);

    PyObject *limits = PyImport_ImportModule("limits");
    PyObject *check_fn = limits ? PyObject_GetAttrString(limits, "check") : NULL;
    PyObject *frame_fn = limits ? PyObject_GetAttrString(limits, "frame_ok") : NULL;
    if (check_fn == NULL || frame_fn == NULL) {
        report("import limits");
        not_passed = -1;
    } else {
        const uint8_t good[] = {'1', '2', '3', '4', '5', '6',
                                '7', '8', '9', 0x29, 0xB1};
        uint8_t bad[sizeof good];
        for (size_t i = 0; i < sizeof good; i++) {
            bad[i] = good[i];
        }
        bad[3] ^= 0x01;  /* one flipped bit in the payload */

        not_passed += check(check_fn, "supply_mv", 3301) != 0;
        not_passed += check(check_fn, "supply_mv", 3601) != 0;
        not_passed += check(check_fn, "temperature_cdeg", -1234) != 0;
        /* "voltage" is not in the table: KeyError */
        not_passed += check(check_fn, "voltage", 3.3) != 0;
        not_passed += frame_ok(frame_fn, "good frame", good, sizeof good) != 0;
        not_passed +=
            frame_ok(frame_fn, "frame with one bit flipped", bad, sizeof bad) != 0;

        /* Release the GIL so that the worker can take it, wait for the worker, take
         * it back. Without PyEval_SaveThread() the main thread holds the GIL while it
         * waits in pthread_join(), and the worker waits in PyGILState_Ensure()
         * forever. */
        struct worker_job job = {check_fn, 0};
        pthread_t worker;
        PyThreadState *saved = PyEval_SaveThread();
        int err = pthread_create(&worker, NULL, worker_main, &job);
        if (err == 0) {
            pthread_join(worker, NULL);
        }
        PyEval_RestoreThread(saved);  /* only this thread may call Python again */
        if (err != 0) {
            fprintf(stderr, "pthread_create failed: %d\n", err);
            not_passed += 1;
        }
        not_passed += job.not_passed;
    }

    Py_XDECREF(check_fn);
    Py_XDECREF(frame_fn);
    Py_XDECREF(limits);
    int rc = Py_FinalizeEx();  /* runs atexit handlers, flushes, frees everything */
    printf("not passed: %d, finalize: %d\n", not_passed, rc);
    return not_passed != 0 || rc < 0;
}
