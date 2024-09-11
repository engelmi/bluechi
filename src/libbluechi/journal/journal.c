#include <systemd/sd-journal.h>

#include "libbluechi/log/log.h"

void setup_journal() {
        sd_journal *journal = NULL;
        int r = sd_journal_open(&journal, SD_JOURNAL_SYSTEM);
        if (r < 0) {
                bc_log_errorf("Failed to open journal: %s", strerror(-r));
                return;
        }

        SD_JOURNAL_FOREACH(journal) {
                const char *d;
                size_t l;

                r = sd_journal_get_data(journal, "MESSAGE", (const void **) &d, &l);
                if (r < 0) {
                        bc_log_errorf("Failed to read message field: %s\n", strerror(-r));
                        continue;
                }

                bc_log_infof("%.*s\n", (int) l, d);
        }

        sd_journal_close(journal);
}
