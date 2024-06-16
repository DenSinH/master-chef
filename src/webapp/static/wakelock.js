$(document).ready(function() {
    const $wakeLockSwitch = $('#wakeLockSwitch');
    let wakeLock = null;

    const requestWakeLock = async () => {
        try {
            wakeLock = await navigator.wakeLock.request('screen');
        } catch (err) {
            console.error(`Failed to activate Wake Lock: ${err.name}, ${err.message}`);
        }
    };

    const releaseWakeLock = () => {
        if (wakeLock !== null) {
            wakeLock.release().then(() => {
                wakeLock = null;
            });
        }
    };

    $wakeLockSwitch.change(function() {
        if (this.checked) {
            requestWakeLock();
        } else {
            releaseWakeLock();
        }
    });

    // Re-request wake lock on visibility change (necessary on some devices)
    $(document).on('visibilitychange', function() {
        if (wakeLock !== null && document.visibilityState === 'visible') {
            requestWakeLock();
        }
    });
});
