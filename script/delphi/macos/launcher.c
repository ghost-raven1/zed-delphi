/* Keep Finder and CLI launches in the Delphi fork's own data directory. */
#include <mach-o/dyld.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char executable[PATH_MAX], resolved[PATH_MAX], data_dir[PATH_MAX];
    uint32_t length = sizeof(executable);
    if (_NSGetExecutablePath(executable, &length) != 0 ||
        realpath(executable, resolved) == NULL) {
        fprintf(stderr, "Zed Delphi: cannot resolve launcher path\n");
        return 1;
    }
    char *slash = strrchr(resolved, '/');
    if (!slash || (size_t)(slash - resolved) + sizeof("/zed-editor") > sizeof(resolved)) {
        fprintf(stderr, "Zed Delphi: executable path too long\n");
        return 1;
    }
    strcpy(slash, "/zed-editor");
    int explicit_dir = 0;
    for (int i = 1; i < argc && strcmp(argv[i], "--") != 0; ++i) {
        if (strcmp(argv[i], "--user-data-dir") == 0 ||
            strncmp(argv[i], "--user-data-dir=", 16) == 0) explicit_dir = 1;
    }
    if (!explicit_dir) {
        const char *home = getenv("HOME");
        if (!home || !*home || home[0] != '/') {
            fprintf(stderr, "Zed Delphi: HOME must be a nonempty absolute path\n");
            return 1;
        }
        int written = snprintf(data_dir, sizeof(data_dir), "%s/Library/Application Support/Zed Delphi", home);
        if (written < 0 || (size_t)written >= sizeof(data_dir)) {
            fprintf(stderr, "Zed Delphi: data directory path too long\n");
            return 1;
        }
    }
    char **args = calloc((size_t)argc + 3, sizeof(char *));
    if (!args) {
        fprintf(stderr, "Zed Delphi: cannot allocate arguments\n");
        return 1;
    }
    int next = 0;
    args[next++] = resolved;
    if (!explicit_dir) {
        args[next++] = "--user-data-dir";
        args[next++] = data_dir;
    }
    for (int i = 1; i < argc; ++i) args[next++] = argv[i];
    execv(resolved, args);
    fprintf(stderr, "Zed Delphi: cannot launch editor: %s\n", strerror(errno));
    free(args);
    return 1;
}
