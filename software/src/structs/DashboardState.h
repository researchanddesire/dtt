#ifndef DASHBOARD_STATE_H
#define DASHBOARD_STATE_H

struct DashboardState {
    bool isPaired = true;
    bool hasUpdate = false;
    bool preflightPending = true;
};

#endif  // DASHBOARD_STATE_H
