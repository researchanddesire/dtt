#ifndef MACHINE_HPP
#define MACHINE_HPP
#include <services/handles.h>

#include "actions.hpp"
#include "boost/sml.hpp"
#include "events.hpp"
#include "guards.hpp"
#ifndef PROVISION
#include "pages/welcome/page.h"
#endif

namespace sml = boost::sml;

struct dtt_state_machine {
    auto operator()() const {
        using namespace sml;

        // clang-format off
        return make_transition_table(
#ifdef PROVISION
            *"init"_s + event<preflight_done>[isOnline<preflight_done>] = "provisioning"_s,
            *"init"_s + event<preflight_done> = "provisioning.wifiSettings"_s,
            *"init"_s + event<force_update> = "update"_s,
            "init.idle"_s = X,

            "provisioning.wifiSettings"_s + on_entry<_> / (drawPage(&wifiSetupPage), startTask(processWifiTask, processWifiTaskName, &processWifiTaskHandle, 20)),
            "provisioning.wifiSettings"_s + event<button_pressed>[isWifiConnected<button_pressed>] / espRestart = X,
            "provisioning.wifiSettings"_s + event<wifi_configured> / espRestart = X,

            "provisioning"_s + on_entry<_> / (drawPage(&provisioningPage), startTask(provisionTask, provisionTaskName, &provisionTaskHandle)),
            "provisioning"_s + event<provision_complete> = "update"_s,
            "provisioning"_s + event<provision_failed> = "provisioning.error"_s,

            "provisioning.error"_s + on_entry<_> / drawProvisionError,
            "provisioning.error"_s + event<button_pressed> = "provisioning"_s,

            "provisioning.done"_s + on_entry<_> / drawProvisionSuccess,
            "provisioning.done"_s + event<button_pressed> = "update"_s,
            "provisioning.done"_s + event<force_update> = "update"_s,

            "update"_s + on_entry<_> / (drawPage(&updateDevicePage), updateDevice),
            "update"_s + event<update_complete> = "provisioning.done"_s,
            "update"_s + event<update_failed> = "provisioning.update_error"_s,

            "provisioning.update_error"_s + on_entry<_> / drawProvisionUpdateError,
            "provisioning.update_error"_s + event<button_pressed> = "update"_s,
            "provisioning.update_error"_s + event<force_update> = "update"_s

#else
#ifdef DEBUG_GO_STRAIGHT_TO_PLAY
            *"init"_s + event<done> = "play.loadSettings"_s,
#else
            *"init"_s + event<done> / startTask(drawWelcomeTask, welcomeTaskName, &welcomeTaskHandle) = "init.idle"_s,
#endif
            "init.idle"_s + event<button_long_pressed> = "wifiSettings"_s,
            "init.idle"_s + event<request_pairing>[isOnline<request_pairing>] = "pairing"_s,
            "init.idle"_s + event<request_pairing> = "wifiSettings"_s,
            "init.idle"_s + event<force_update> = "update"_s,
            "init.idle"_s + event<button_pressed> = "init.preflight"_s,
            "init.idle"_s + event<timeout_expired> = "init.preflight"_s,
            "init.idle"_s + sml::on_exit<_> / (clear),

            "init.preflight"_s + on_entry<_> / (drawPage(&preflightPage), preflightCheck),
            "init.preflight"_s + event<preflight_done>[isOnline<preflight_done> && !hasTrainerId<preflight_done>] = "provisioning"_s,
            "init.preflight"_s + event<preflight_done>[isOnline<preflight_done> && hasUpdate<preflight_done>] = "update"_s,
            "init.preflight"_s + event<preflight_done>[isOnline<preflight_done> && !isPaired<preflight_done>] = "pairing"_s,
            "init.preflight"_s + event<preflight_done> = "play.preflight"_s,
            "init.preflight"_s + sml::on_exit<_> / (clear),

            "provisioning.wifiSettings"_s = X,

            // Stored identity is blank (erased NVS): fetch it by hardware
            // address, then reboot so preflight runs with a real trainer ID.
            "provisioning"_s + on_entry<_> / (drawPage(&provisioningPage), startTask(provisionTask, provisionTaskName, &provisionTaskHandle)),
            "provisioning"_s + event<provision_complete> / espRestart = X,
            "provisioning"_s + event<provision_failed> = "provisioning.error"_s,
            "provisioning"_s + event<timeout_expired> / provisionTimedOut = "provisioning.error"_s,

            "provisioning.error"_s + on_entry<_> / drawProvisionError,
            "provisioning.error"_s + event<button_pressed> = "provisioning"_s,

            "pairing"_s + on_entry<_> / (drawPage(&pairingPage), startTask(checkIfPairedTask, checkIfPairedTaskName, &checkIfPairedTaskHandle, RUNTIME_TASK_STACK_MULTIPLIER)),
            "pairing"_s + event<done> = "play.preflight"_s,
            "pairing"_s + event<button_pressed> = "play.preflight"_s,
            "pairing"_s + event<timeout_expired> = "play.preflight"_s,
            "pairing"_s + sml::on_exit<_> / (clear),

            "wifiSettings"_s + on_entry<_> / (drawPage(&wifiSetupPage), startTask(processWifiTask, processWifiTaskName, &processWifiTaskHandle, RUNTIME_TASK_STACK_MULTIPLIER)),
            "wifiSettings"_s + event<button_pressed> / espRestart = X,
            "wifiSettings"_s + event<done> / espRestart = X,

            "update"_s + on_entry<_> / (drawPage(&updateDevicePage), updateDevice),
            "update"_s + event<fail> = "init.preflight"_s,

            "play.preflight"_s + on_entry<_> / drawPage(&preflightPage),
            "play.preflight"_s + event<done>[isOnline<done> && isPaired<done>] = "play.fetchSettings"_s,
            "play.preflight"_s + event<done>[isOnline<done> && !isPaired<done>] = "play.loadSettings"_s,
            "play.preflight"_s + event<done>[isWifiConnected<done> && !isHealthCheckPassed<done>] = "play.bad_health_check"_s,
            "play.preflight"_s + event<done> = "play.loadSettings"_s,
            "play.preflight"_s + event<force_update> = "update"_s,

            "play.bad_health_check"_s + on_entry<_> / (drawPage(&badHealthCheckPage), disconnectWifi),
            "play.bad_health_check"_s + event<button_pressed> = "play.loadSettings"_s,
            "play.bad_health_check"_s + sml::on_exit<_> / (clear),

            "play.fetchSettings"_s + on_entry<_> / (drawPage(&fetchingSettingsPage), startTask(fetchSettingsTask, fetchSettingsTaskName, &fetchSettingsTaskHandle, RUNTIME_TASK_STACK_MULTIPLIER)),
            "play.fetchSettings"_s + event<session_load_ready> / applyLoadedSession,
            "play.fetchSettings"_s + event<session_load_failed> / failSessionLoad,
            "play.fetchSettings"_s + event<done>[isCalibrated<done>] = "play.ready"_s,
            "play.fetchSettings"_s + event<done>[!isCalibrated<done>] = "play.calibration.min"_s,
            "play.fetchSettings"_s + event<fail>[!isHealthCheckPassed<fail>] = "play.bad_health_check"_s,
            "play.fetchSettings"_s + event<fail> = "play.loadSettings"_s,

            #ifdef AUTOPLAY_FOR_VIDEO
            "play.loadSettings"_s + on_entry<_> / (beginSessionLoad, startTask(loadSessionTask, loadSessionTaskName, &loadSessionTaskHandle, RUNTIME_TASK_STACK_MULTIPLIER)),
            "play.loadSettings"_s + event<done>[isSessionLoadComplete<done>] = "play"_s,
            #else
            "play.loadSettings"_s + on_entry<_> / (beginSessionLoad, drawLoadSettingsPage, startTask(loadSessionTask, loadSessionTaskName, &loadSessionTaskHandle, RUNTIME_TASK_STACK_MULTIPLIER)),
            #endif
            "play.loadSettings"_s + event<session_load_ready> / applyLoadedSession,
            "play.loadSettings"_s + event<session_load_failed> / failSessionLoad,
            "play.loadSettings"_s + event<fail> / recoverMissingSegment,
            "play.loadSettings"_s + event<button_long_pressed>[isSessionLoadComplete<button_long_pressed>] = "play"_s,
            "play.loadSettings"_s + event<button_pressed>[isSessionLoadComplete<button_pressed> && isCalibrated<button_pressed>] = "play.ready"_s,
            "play.loadSettings"_s + event<button_pressed>[isSessionLoadComplete<button_pressed> && !isCalibrated<button_pressed>] = "play.calibration.min"_s,
            "play.loadSettings"_s + event<timeout_expired>[isSessionLoadComplete<timeout_expired> && isCalibrated<timeout_expired>] = "play.ready"_s,
            "play.loadSettings"_s + event<timeout_expired>[isSessionLoadComplete<timeout_expired> && !isCalibrated<timeout_expired>] = "play.calibration.min"_s,
            "play.loadSettings"_s + event<force_update> = "update"_s,

            "play.calibration.min"_s + on_entry<_> / drawPage(&calibrationMinPage),
            "play.calibration.min"_s + event<button_pressed> / captureMinPosition = "play.calibration.max"_s,

            "play.calibration.max"_s + on_entry<_> / drawPage(&calibrationMaxPage),
            "play.calibration.max"_s + event<button_pressed> = "play.calibration.check"_s,

            "play.calibration.check"_s + on_entry<_> / captureMaxPosition,
            "play.calibration.check"_s + event<done> = "play.ready"_s,
            "play.calibration.check"_s + event<fail> = "play.calibration.invalid"_s,

            "play.calibration.invalid"_s + on_entry<_> / drawCalibrationProblem,
            "play.calibration.invalid"_s + event<button_pressed> = "play.calibration.min"_s,
            "play.calibration.invalid"_s + event<button_long_pressed>[isCalibrated<button_long_pressed>] = "play.ready"_s,

            "play.ready"_s + on_entry<_> / next,
            "play.ready"_s + event<done>[hasSeenSessionDetails<done>] = "play.details.segment"_s,
            "play.ready"_s + event<done> = "play.details.session"_s,

            "play.details.session"_s + on_entry<_> / (drawSessionDetails),
            "play.details.session"_s + event<session_replace_requested> / applyRequestedSession,
            "play.details.session"_s + event<controller_released> = "play.details.session"_s,
            "play.details.session"_s + event<button_long_pressed> = "play"_s,
            "play.details.session"_s + event<timeout_expired>[isHandsFreeMode<timeout_expired>] = "play"_s,
            "play.details.session"_s + event<button_pressed>[hasSeenSessionDetails<button_pressed>] = "play"_s,
            "play.details.session"_s + event<button_pressed>[hasToy<button_pressed>] = "play.details.toy"_s,
            "play.details.session"_s + event<button_pressed> = "play.details.segment"_s,
            "play.details.session"_s + event<timeout_expired>[hasToy<timeout_expired>] = "play.details.toy"_s,
            "play.details.session"_s + event<timeout_expired> = "play.details.segment"_s,
            "play.details.session"_s + event<force_update> = "update"_s,

            "play.details.toy"_s + on_entry<_> / (drawToyDetails),
            "play.details.toy"_s + event<session_replace_requested> / applyRequestedSession,
            "play.details.toy"_s + event<button_long_pressed> = "play"_s,
            "play.details.toy"_s + event<button_pressed>[hasSeenSessionDetails<button_pressed>] = "play"_s,
            "play.details.toy"_s + event<button_pressed> = "play.details.segment"_s,
            "play.details.toy"_s + event<controller_released> = "play.details.session"_s,
            "play.details.toy"_s + event<timeout_expired> = "play.details.segment"_s,
            "play.details.toy"_s + event<force_update> = "update"_s,

            "play.details.segment"_s + on_entry<_> / (drawSegmentDetails),
            "play.details.segment"_s + event<session_replace_requested> / applyRequestedSession,
            "play.details.segment"_s + event<controller_released> = "play.details.session"_s,
            "play.details.segment"_s + event<fail> / recoverMissingSegment = "play.details.session"_s,
            "play.details.segment"_s + event<button_long_pressed> = "play"_s,
            "play.details.segment"_s + event<button_pressed> = "play"_s,
            #ifdef AUTOPLAY_FOR_VIDEO
            "play.details.segment"_s + event<timeout_expired> = "play"_s,
            #else
            "play.details.segment"_s + event<timeout_expired>[isHandsFreeMode<timeout_expired>] = "play"_s,
            "play.details.segment"_s + event<timeout_expired>[!isHandsFreeMode<timeout_expired>] = "play.details.session"_s,
            #endif
            "play.details.segment"_s + event<force_update> = "update"_s,

            "play"_s + on_entry<_> / (clear, next),
            "play"_s + event<done> = "play.begin"_s,
            "play.begin"_s + on_entry<_> / (drawBegin),
            "play.begin"_s + event<done> = "play.idle"_s,
            "play.begin"_s + event<fail> / recoverMissingSegment = "play.details.session"_s,

            "play.idle"_s + on_entry<_> / (clear, startTrainingRun),
            "play.idle"_s + sml::on_exit<_> / stopTraining,
            "play.idle"_s + event<training_worker_finished>[completedTrainingWorker] = "play.grade"_s,
            // Short of memory: keep the session and its calibration, and go back
            // to the segment so it can be started again.
            "play.idle"_s + event<training_worker_failed>[currentWorkerOutOfMemory] = "play.details.segment"_s,
            "play.idle"_s + event<training_worker_failed>[currentTrainingWorker] / recoverMissingSegment = "play.details.session"_s,
            "play.idle"_s + event<recalibrate> = "play.calibration.min"_s,
            // Leaving play.idle stops the run and the vibrator; clear drops the
            // segment and its LED. The session and calibration stay as they are.
            "play.idle"_s + event<end_segment> / clear = "play.details.segment"_s,
            #ifdef BYPASS_PLAY
            "play.idle"_s + event<button_long_pressed> = "play.grade"_s,
            #endif

            "play.grade"_s + on_entry<_> / (drawGradeOrFailure, saveCompletedResult),
            "play.grade"_s + event<button_pressed> / evaluatePassFail,
            "play.grade"_s + event<timeout_expired> / evaluatePassFail,
            "play.grade"_s + event<segment_failed> = "play.failed"_s,
            "play.grade"_s + event<three_strikes> = "play.threestrikes"_s,
            "play.grade"_s + event<done>[hasNext<done> && isNextLoaded<done>] / incrementSegmentIdx = "play.details.segment"_s,
            "play.grade"_s + event<done>[hasNext<done> && !isNextLoaded<done>] / incrementSegmentIdx = "play.preflight"_s,
            "play.grade"_s + event<done>[!hasNext<done>] = "play.final"_s,

            "play.failed"_s + on_entry<_> / next,
            "play.failed"_s + event<done> / retrySegment = "play.details.segment"_s,

            "play.threestrikes"_s + on_entry<_> / drawThreeStrikesScreen,
            "play.threestrikes"_s + event<button_pressed> / restartTraining = "play.preflight"_s,
            "play.threestrikes"_s + event<timeout_expired> / restartTraining = "play.preflight"_s,
            "play.threestrikes"_s + event<restart_training> / restartTraining = "play.preflight"_s,

            "play.final"_s + on_entry<_> / drawFinalPage,
            "play.final"_s + event<button_pressed> / clearSegmentIndex = "play.preflight"_s,
            "play.final"_s + event<timeout_expired> / clearSegmentIndex = "play.preflight"_s,
            "play.final"_s + event<restart_training> / restartTraining = "play.preflight"_s
#endif  // PROVISION
        );
        // clang-format on
    }
};

#endif
