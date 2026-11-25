(function () {
    var storageKey = "slp-theme";

    function getTheme() {
        return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    }

    function updateToggle(theme) {
        var icon = theme === "dark" ? "sun" : "moon";
        var label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
            button.setAttribute("aria-label", label);
            button.setAttribute("title", label);
            button.innerHTML = '<i data-lucide="' + icon + '"></i>';
        });
        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons();
        }
    }

    function applyTheme(theme, persist) {
        if (theme !== "light" && theme !== "dark") return;
        document.documentElement.setAttribute("data-theme", theme);
        document.documentElement.setAttribute("data-bs-theme", theme);
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", theme === "dark" ? "#17132B" : "#F5F3FF");
        if (persist) {
            try {
                localStorage.setItem(storageKey, theme);
            } catch (error) {
            }
        }
        updateToggle(theme);
        window.dispatchEvent(new CustomEvent("slp:themechange", { detail: { theme: theme } }));
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            button.addEventListener("click", function () {
                applyTheme(getTheme() === "dark" ? "light" : "dark", true);
            });
        });
        updateToggle(getTheme());
    });

    window.addEventListener("storage", function (event) {
        if (event.key === storageKey && (event.newValue === "light" || event.newValue === "dark")) {
            applyTheme(event.newValue, false);
        }
    });
})();
