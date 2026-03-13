document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("stockSearchInput");
    const items = document.querySelectorAll(".stock-item");
    const emptyMessage = document.getElementById("stockEmptyMessage");

    if (!input) return;

    input.addEventListener("input", function () {
        const keyword = this.value.trim().toLowerCase();
        let visibleCount = 0;

        items.forEach(item => {
            const name = item.dataset.name || "";
            const ticker = item.dataset.ticker || "";

            const matched = name.includes(keyword) || ticker.includes(keyword);

            if (matched) {
                item.style.display = "block";
                visibleCount++;
            } else {
                item.style.display = "none";
            }
        });

        emptyMessage.style.display = visibleCount === 0 ? "block" : "none";
    });

    document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach(btn => {
        btn.addEventListener("shown.bs.dropdown", function () {
            setTimeout(() => input.focus(), 100);
        });
    });
});