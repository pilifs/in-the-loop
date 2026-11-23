#define _GNU_SOURCE
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* Start the measured process from a small executable. Linux child peak RSS can
   otherwise include the Python interpreter that forks before exec. */
int main(int argc, char **argv) {
    if (argc < 3) return 125;
    struct timespec start, end;
    struct rusage usage;
    int status;
    if (clock_gettime(CLOCK_MONOTONIC, &start)) return 125;
    pid_t pid = fork();
    if (pid < 0) return 125;
    if (pid == 0) {
        execvp(argv[2], argv + 2);
        perror("execvp");
        _exit(127);
    }
    while (wait4(pid, &status, 0, &usage) < 0)
        if (errno != EINTR) return 125;
    if (clock_gettime(CLOCK_MONOTONIC, &end)) return 125;
    FILE *out = fopen(argv[1], "w");
    if (!out) return 125;
    double seconds = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    if (fprintf(out, "%ld %.9f\n", usage.ru_maxrss, seconds) < 0 || fclose(out)) return 125;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
