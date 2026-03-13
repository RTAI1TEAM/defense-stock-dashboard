const sortOrders = {};

function sortTable(tableId, colIndex) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));

    const key = `${tableId}_${colIndex}`;
    const asc = sortOrders[key] === undefined ? true : !sortOrders[key];
    sortOrders[key] = asc;

    rows.sort((a, b) => {
        let x = a.cells[colIndex].innerText.trim();
        let y = b.cells[colIndex].innerText.trim();

        let xVal = x.replace(/[^0-9.-]+/g, "");
        let yVal = y.replace(/[^0-9.-]+/g, "");

        let xFinal = xVal !== "" && !isNaN(parseFloat(xVal)) ? parseFloat(xVal) : x.toLowerCase();
        let yFinal = yVal !== "" && !isNaN(parseFloat(yVal)) ? parseFloat(yVal) : y.toLowerCase();

        if (xFinal < yFinal) return asc ? -1 : 1;
        if (xFinal > yFinal) return asc ? 1 : -1;
        return 0;
    });

    rows.forEach(row => tbody.appendChild(row));
    updateRank(tableId);
}

function updateRank(tableId) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    rows.forEach((row, index) => {
        row.cells[0].innerText = index + 1;
    });
}