#pragma once

namespace firmware {

enum class UpdateAction {
    resolve,
    complete,
    install,
    reject,
};

constexpr UpdateAction selectUpdateAction(const bool decisionValid,
                                          const bool shouldUpdate,
                                          const bool installRequired = false) {
    if (!decisionValid) return UpdateAction::resolve;
    if (shouldUpdate) return UpdateAction::install;
    return installRequired ? UpdateAction::reject : UpdateAction::complete;
}

}  // namespace firmware
