#include "libbluechi/journal/journal.h"

#include <errno.h>
#include <stdio.h>
#include <systemd/sd-journal.h>

int main() {
        int r;
        sd_journal *j;

        r = sd_journal_open(&j, SD_JOURNAL_SYSTEM | SD_JOURNAL_CURRENT_USER | SD_JOURNAL_ALL_NAMESPACES);
        if (r < 0) {
                fprintf(stderr, "Failed to open journal: %s\n", strerror(-r));
                return 1;
        }

        const char *field;
        SD_JOURNAL_FOREACH_FIELD(j, field)
                printf("%s\n", field);

        SD_JOURNAL_FOREACH(j) {
                const char *msg;
                size_t msgsize;
                const char *timestamp;
                size_t timestampsize;

                r = sd_journal_get_data(j, "MESSAGE", (const void **) &msg, &msgsize);
                if (r < 0) {
                        fprintf(stderr, "Failed to read message field: %s\n", strerror(-r));
                        continue;
                }
                r = sd_journal_get_data(
                                j, "_SOURCE_REALTIME_TIMESTAMP", (const void **) &timestamp, &timestampsize);
                if (r < 0) {
                        fprintf(stderr, "Failed to read timestamp field: %s\n", strerror(-r));
                        continue;
                }

                printf("%.*s: %.*s\n", (int) timestampsize, timestamp, (int) msgsize, msg);
        }

        fprintf(stdout, "Closing journal...\n");
        sd_journal_close(j);
}
