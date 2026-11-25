(function () {
    var dialog = document.getElementById('mdConfirmDialog');
    var pending = null;

    function showDialog(message, onConfirm) {
        if (!dialog || typeof dialog.showModal !== 'function') {
            if (window.confirm(message)) onConfirm();
            return;
        }
        var text = dialog.querySelector('[data-md-dialog-text]');
        if (text) text.textContent = message;
        pending = onConfirm;
        dialog.showModal();
    }

    document.querySelectorAll('[data-md-snackbar]').forEach(function (bar) {
        var close = function () {
            bar.classList.add('is-hiding');
            window.setTimeout(function () { bar.remove(); }, 220);
        };
        var timer = window.setTimeout(close, 5500);
        var button = bar.querySelector('[data-md-snackbar-close]');
        if (button) {
            button.addEventListener('click', function () {
                window.clearTimeout(timer);
                close();
            });
        }
    });

    document.addEventListener('click', function (event) {
        var dismiss = event.target.closest('[data-md-banner-close]');
        if (dismiss) {
            var banner = dismiss.closest('.md-banner');
            if (banner) banner.remove();
        }

        var trigger = event.target.closest('a[data-confirm]');
        if (!trigger || trigger.dataset.mdConfirmed === 'true') return;
        event.preventDefault();
        showDialog(trigger.getAttribute('data-confirm'), function () {
            trigger.dataset.mdConfirmed = 'true';
            window.location.assign(trigger.href);
        });
    });

    document.addEventListener('submit', function (event) {
        var form = event.target;
        var trigger = form.querySelector('[data-confirm]');
        if (!trigger || form.dataset.mdConfirmed === 'true') return;
        event.preventDefault();
        showDialog(trigger.getAttribute('data-confirm'), function () {
            form.dataset.mdConfirmed = 'true';
            if (form.requestSubmit) form.requestSubmit(); else form.submit();
        });
    });

    if (dialog) {
        var confirmButton = dialog.querySelector('[data-md-dialog-confirm]');
        if (confirmButton) {
            confirmButton.addEventListener('click', function () {
                dialog.close();
                var action = pending;
                pending = null;
                if (action) action();
            });
        }
        dialog.querySelectorAll('[data-md-dialog-cancel], [data-md-dialog-close]').forEach(function (button) {
            button.addEventListener('click', function () {
                dialog.close();
                pending = null;
            });
        });
    }
})();
