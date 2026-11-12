/* The only file that knows about Python: the firmware's CRC and COBS as a CPython module. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "fw/cobs.h"
#include "fw/crc16.h"

/* limit: the longest input accepted. FW_MAX_FRAME comes from the firmware's CMake target. */
static int get_frame(PyObject *arg, Py_buffer *view, Py_ssize_t limit)
{
    if (PyObject_GetBuffer(arg, view, PyBUF_SIMPLE) < 0) {
        return -1;   /* TypeError already set, for example for str */
    }
    if (view->len > limit) {
        Py_ssize_t len = view->len;   /* copy before the release: the view is invalid afterwards */
        PyBuffer_Release(view);
        PyErr_Format(PyExc_ValueError, "%zd bytes is longer than the limit of %zd for FW_MAX_FRAME (%d)",
                     len, limit, FW_MAX_FRAME);
        return -1;
    }
    return 0;
}

static PyObject *py_crc16(PyObject *module, PyObject *arg)
{
    (void)module;
    Py_buffer view;
    if (get_frame(arg, &view, FW_MAX_FRAME) < 0) {
        return NULL;
    }
    uint16_t crc = crc16_ccitt((const uint8_t *)view.buf, (size_t)view.len);
    PyBuffer_Release(&view);
    return PyLong_FromUnsignedLong(crc);
}

static PyObject *py_cobs_encode(PyObject *module, PyObject *arg)
{
    (void)module;
    Py_buffer view;
    if (get_frame(arg, &view, FW_MAX_FRAME) < 0) {
        return NULL;
    }
    size_t len = (size_t)view.len;
    PyObject *out = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)COBS_MAX_ENCODED(len));
    if (out != NULL) {
        size_t n = cobs_encode((const uint8_t *)view.buf, len, (uint8_t *)PyBytes_AS_STRING(out));
        if (_PyBytes_Resize(&out, (Py_ssize_t)n) < 0) {
            out = NULL;
        }
    }
    PyBuffer_Release(&view);
    return out;
}

static PyObject *py_cobs_decode(PyObject *module, PyObject *arg)
{
    (void)module;
    Py_buffer view;
    if (get_frame(arg, &view, (Py_ssize_t)COBS_MAX_ENCODED(FW_MAX_FRAME)) < 0) {
        return NULL;   /* an encoded frame is a little longer than the frame it holds */
    }
    PyObject *out = PyBytes_FromStringAndSize(NULL, view.len);
    if (out != NULL) {
        size_t n = cobs_decode((const uint8_t *)view.buf, (size_t)view.len,
                               (uint8_t *)PyBytes_AS_STRING(out));
        if (n == COBS_ERROR) {
            Py_DECREF(out);
            out = NULL;
            PyErr_SetString(PyExc_ValueError, "invalid COBS data");
        } else if (_PyBytes_Resize(&out, (Py_ssize_t)n) < 0) {
            out = NULL;
        }
    }
    PyBuffer_Release(&view);
    return out;
}

static PyMethodDef methods[] = {
    {"crc16", py_crc16, METH_O, "CRC-16/CCITT-FALSE of a bytes-like object."},
    {"cobs_encode", py_cobs_encode, METH_O, "COBS-encode a bytes-like object."},
    {"cobs_decode", py_cobs_decode, METH_O, "COBS-decode a bytes-like object."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT, "_fwcore", "The firmware's fw_core library.", 0, methods,
};

PyMODINIT_FUNC PyInit__fwcore(void)
{
    PyObject *m = PyModule_Create(&module_def);
    if (m == NULL) {
        return NULL;
    }
    if (PyModule_AddIntConstant(m, "MAX_FRAME", FW_MAX_FRAME) < 0) {
        Py_DECREF(m);
        return NULL;
    }
#ifdef Py_GIL_DISABLED
    PyUnstable_Module_SetGIL(m, Py_MOD_GIL_NOT_USED);   /* the functions keep no shared state */
#endif
    return m;
}
