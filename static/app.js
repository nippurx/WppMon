(function () {
    const REFRESH_INTERVAL_MS = 5000;

    const shouldPauseReload = () => {
        const active = document.activeElement;
        if (!active) {
            return false;
        }

        const tag = active.tagName;
        if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") {
            return true;
        }

        if (active.isContentEditable) {
            return true;
        }

        if (typeof active.closest === "function" && active.closest("form")) {
            return true;
        }

        return false;
    };

    setInterval(() => {
        if (shouldPauseReload()) {
            return;
        }
        window.location.reload();
    }, REFRESH_INTERVAL_MS);
})();
