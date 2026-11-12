/* A C extension with one piece of shared mutable state, in 3 versions of "add n to it".
 * Built twice: _counter declares that it is safe without the GIL, _counter_gil does not.
 * Run with freethreading_demo.py. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdatomic.h>

#define STR_(x) #x
#define STR(x) STR_(x)

static volatile long long plain_count;  /* volatile: every ++ is a real load, add and store */
static atomic_llong atomic_count;
static long long locked_count;
static long long callback_count;
static PyMutex lock;                    /* PyMutex: public API since Python 3.13 */

/* Holds the GIL for the whole call on a normal build, so other Python threads cannot interleave.
 * With the GIL gone, 2 threads can be inside this loop at once. */
static PyObject *bump_plain(PyObject *self, PyObject *arg)
{
    (void)self;
    long long n = PyLong_AsLongLong(arg);
    if (n == -1 && PyErr_Occurred()) {
        return NULL;
    }
    for (long long i = 0; i < n; i++) {
        plain_count++;
    }
    Py_RETURN_NONE;
}

static PyObject *bump_atomic(PyObject *self, PyObject *arg)
{
    (void)self;
    long long n = PyLong_AsLongLong(arg);
    if (n == -1 && PyErr_Occurred()) {
        return NULL;
    }
    for (long long i = 0; i < n; i++) {
        atomic_fetch_add_explicit(&atomic_count, 1, memory_order_relaxed);
    }
    Py_RETURN_NONE;
}

static PyObject *bump_locked(PyObject *self, PyObject *arg)
{
    (void)self;
    long long n = PyLong_AsLongLong(arg);
    if (n == -1 && PyErr_Occurred()) {
        return NULL;
    }
    for (long long i = 0; i < n; i++) {
        PyMutex_Lock(&lock);
        locked_count++;
        PyMutex_Unlock(&lock);
    }
    Py_RETURN_NONE;
}

/* Reads the counter, calls back into Python, then stores the result. Running Python code lets
 * the interpreter switch threads, so the GIL does not make this update a single step. */
static PyObject *bump_callback(PyObject *self, PyObject *args)
{
    (void)self;
    long long n;
    PyObject *callback;
    if (!PyArg_ParseTuple(args, "LO", &n, &callback)) {
        return NULL;
    }
    for (long long i = 0; i < n; i++) {
        long long seen = callback_count;
        PyObject *result = PyObject_CallNoArgs(callback);
        if (result == NULL) {
            return NULL;
        }
        Py_DECREF(result);
        callback_count = seen + 1;
    }
    Py_RETURN_NONE;
}

static PyObject *values(PyObject *self, PyObject *Py_UNUSED(ignored))
{
    (void)self;
    PyMutex_Lock(&lock);
    long long locked = locked_count;
    PyMutex_Unlock(&lock);
    return Py_BuildValue("(LLLL)", (long long)plain_count,
                         (long long)atomic_load(&atomic_count), locked, callback_count);
}

static PyObject *reset(PyObject *self, PyObject *Py_UNUSED(ignored))
{
    (void)self;
    plain_count = 0;
    atomic_store(&atomic_count, 0);
    PyMutex_Lock(&lock);
    locked_count = 0;
    callback_count = 0;
    PyMutex_Unlock(&lock);
    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
    {"bump_plain", bump_plain, METH_O, "Add n with a plain ++ (not thread safe)."},
    {"bump_atomic", bump_atomic, METH_O, "Add n with an atomic increment."},
    {"bump_locked", bump_locked, METH_O, "Add n under a PyMutex."},
    {"bump_callback", bump_callback, METH_VARARGS, "Add n, calling a Python function each time."},
    {"values", values, METH_NOARGS, "Return (plain, atomic, locked, callback)."},
    {"reset", reset, METH_NOARGS, "Set all 4 counters to 0."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    .m_base = PyModuleDef_HEAD_INIT, .m_name = STR(MODULE_NAME), .m_size = -1, .m_methods = methods,
};

#define CONCAT_(a, b) a##b
#define CONCAT(a, b) CONCAT_(a, b)

PyMODINIT_FUNC CONCAT(PyInit_, MODULE_NAME)(void)
{
    PyObject *m = PyModule_Create(&module_def);
#if defined(Py_GIL_DISABLED) && defined(DECLARE_NO_GIL)
    /* The promise: this module protects its own state, so import does not re-enable the GIL.
     * Only _counter makes it, and only the atomic and locked versions keep it. */
    if (m != NULL) {
        PyUnstable_Module_SetGIL(m, Py_MOD_GIL_NOT_USED);
    }
#endif
    return m;
}
