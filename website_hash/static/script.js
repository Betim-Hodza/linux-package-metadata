// static/script.js
document.addEventListener("DOMContentLoaded", () => {
    const searchBox = document.getElementById("searchBox");
    const searchBtn = document.getElementById("searchBtn");
    const tableBody = document.querySelector("#resultTable tbody");
    const headers   = document.querySelectorAll("#resultTable th");
    const pagerDiv  = document.getElementById("pager");

    // -----------------------------------------------------------------
    // Pagination state
    // -----------------------------------------------------------------
    let currentPage = 1;
    const pageSize = 50;               // must match backend DEFAULT_LIMIT
    let totalRows = 0;

    // -----------------------------------------------------------------
    // Sorting state
    // -----------------------------------------------------------------
    let currentSort = { col: "name", order: "asc" };

    // -----------------------------------------------------------------
    // Fetch data from the API and render it
    // -----------------------------------------------------------------
    async function fetchData() {
        const params = new URLSearchParams({
            q: searchBox.value.trim(),
            sort_by: currentSort.col,
            order: currentSort.order,
            page: currentPage,
            limit: pageSize
        });

        const resp = await fetch(`/api/search?${params}`);
        if (!resp.ok) {
            console.error("API error:", resp.status, resp.statusText);
            return;
        }
        const data = await resp.json();   // <-- new shape
        totalRows = data.total;
        renderRows(data.results);
        renderPager();
    }

    // -----------------------------------------------------------------
    // Render the rows into the table body
    // -----------------------------------------------------------------
    function renderRows(rows) {
        tableBody.innerHTML = "";
        rows.forEach(row => {
            const tr = document.createElement("tr");
            // Keep the column order identical to the header order
            ["name", "version", "sha256", "file", "url"].forEach(col => {
                const td = document.createElement("td");
                if (col === "url" && row[col]) {
                    const a = document.createElement("a");
                    a.href = row[col];
                    a.textContent = row[col];
                    a.target = "_blank";
                    td.appendChild(a);
                } else {
                    td.textContent = row[col] ?? "";
                }
                tr.appendChild(td);
            });
            tableBody.appendChild(tr);
        });
    }

    // -----------------------------------------------------------------
    // Pagination UI
    // -----------------------------------------------------------------
    function renderPager() {
        const totalPages = Math.ceil(totalRows / pageSize);
        pagerDiv.innerHTML = `
            Page ${currentPage} of ${totalPages}
            <button ${currentPage===1 ? "disabled" : ""} id="prevBtn">Prev</button>
            <button ${currentPage===totalPages ? "disabled" : ""} id="nextBtn">Next</button>
            (Total rows: ${totalRows})
        `;

        document.getElementById("prevBtn").onclick = () => {
            if (currentPage > 1) {
                currentPage--;
                fetchData();
            }
        };
        document.getElementById("nextBtn").onclick = () => {
            if (currentPage < totalPages) {
                currentPage++;
                fetchData();
            }
        };
    }

    // -----------------------------------------------------------------
    // Search button / Enter key
    // -----------------------------------------------------------------
    searchBtn.addEventListener("click", () => {
        currentPage = 1;          // reset to first page on a new search
        fetchData();
    });
    searchBox.addEventListener("keypress", e => {
        if (e.key === "Enter") {
            currentPage = 1;
            fetchData();
        }
    });

    // -----------------------------------------------------------------
    // Column‑header sorting
    // -----------------------------------------------------------------
    headers.forEach(th => {
        th.addEventListener("click", () => {
            const col = th.dataset.col;
            if (currentSort.col === col) {
                // toggle direction
                currentSort.order = currentSort.order === "asc" ? "desc" : "asc";
            } else {
                currentSort.col = col;
                currentSort.order = "asc";
            }
            // visual cue
            headers.forEach(h => h.classList.remove("sort-asc", "sort-desc"));
            th.classList.add(currentSort.order === "asc" ? "sort-asc" : "sort-desc");

            // keep the same page (or reset to 1 if you prefer)
            fetchData();
        });
    });

    // -----------------------------------------------------------------
    // Initial load
    // -----------------------------------------------------------------
    fetchData();
});
