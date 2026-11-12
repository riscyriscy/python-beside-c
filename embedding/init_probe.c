/* Starts the interpreter the plain way or the isolated way and prints what it loaded.
 * Usage: init_probe plain | isolated | badconfig | where | pinned PROGRAM | sleep-plain | sleep-isolated
 * badconfig asks for an encoding that does not exist, to show the PyStatus path.
 * where prints which interpreter the isolated start found, pinned sets program_name to PROGRAM,
 * and the sleep modes show what SIGINT does while Python code waits. */
#include <Python.h>
#include <stdio.h>
#include <string.h>

static const char REPORT[] =
    "import sys\n"
    "sys.stdout.reconfigure(line_buffering=True)  # keep Python and C lines in order\n"
    "print('  sys.flags.isolated', sys.flags.isolated,\n"
    "      ' sys.flags.no_user_site', sys.flags.no_user_site)\n"
    "import os, statistics  # statistics: any module that the rules file imports\n"
    "where = os.path.basename(os.path.dirname(statistics.__file__))\n"
    "print('  statistics.py found in:', where)\n";

static const char WHERE[] =
    "import sys\n"
    "print('  sys.executable', sys.executable)\n"
    "print('  sys.prefix    ', sys.prefix)\n"
    "print('  site-packages ', [p for p in sys.path if p.endswith('site-packages')])\n";

static const char SLEEP[] =
    "import atexit, time\n"
    "atexit.register(print, '  atexit handler ran', flush=True)\n"
    "print('  sleeping, send SIGINT', flush=True)\n"
    "time.sleep(30)\n";

static int start_isolated(int bad_config, const char *program)
{
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    PyStatus status = PyStatus_Ok();
    if (bad_config) {
        status = PyConfig_SetString(&config, &config.stdio_encoding, L"nosuch");
    }
    if (program != NULL) {  /* pins sys.executable instead of searching PATH for "python3" */
        status = PyConfig_SetBytesString(&config, &config.program_name, program);
    }
    if (!PyStatus_Exception(status)) {
        status = Py_InitializeFromConfig(&config);
    }
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        fprintf(stderr, "start-up failed in %s:\n  %s\n",
                status.func ? status.func : "?", status.err_msg ? status.err_msg : "?");
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s plain|isolated|badconfig|where|pinned PROGRAM|sleep-plain|sleep-isolated\n",
                argv[0]);
        return 2;
    }
    const char *mode = argv[1];
    const char *program = strcmp(mode, "pinned") == 0 && argc == 3 ? argv[2] : NULL;
    if (strcmp(mode, "plain") == 0 || strcmp(mode, "sleep-plain") == 0) {
        Py_Initialize();
    } else if (start_isolated(strcmp(mode, "badconfig") == 0, program) < 0) {
        return 2;
    }
    printf("%s:\n", mode);
    fflush(stdout);
    const char *code = REPORT;
    if (strcmp(mode, "where") == 0 || strcmp(mode, "pinned") == 0) {
        code = WHERE;
    } else if (strncmp(mode, "sleep-", 6) == 0) {
        code = SLEEP;
    }
    int rc = PyRun_SimpleString(code);
    return Py_FinalizeEx() < 0 || rc != 0;
}
