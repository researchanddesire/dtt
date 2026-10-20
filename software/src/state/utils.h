#ifndef STATE_UTILS_H
#define STATE_UTILS_H

void process_done(bool delay = true);
void process_fail();
void process_preflight_done(bool delay = true);
void process_update_complete();
void process_update_failed();
void process_segment_failed();
void process_three_strikes();

#endif  // STATE_UTILS_H
