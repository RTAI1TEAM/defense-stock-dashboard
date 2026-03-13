document.addEventListener("DOMContentLoaded", function(){
    const input = document.getElementById("navbarStockSearch");
    const results = document.getElementById("navbarStockResults");
    const items = document.querySelectorAll(".navbar-stock-item");
    const empty = document.getElementById("navbarEmpty");
    const newsItems = document.querySelectorAll(".news-item");


    if(input){    
        input.addEventListener("input", function(){
            const keyword = this.value.trim().toLowerCase();
            if(keyword === ""){
                results.style.display = "none";
                return;
            }
            results.style.display = "block";
            let visible = 0;
            items.forEach(item => {
                const name = item.dataset.name;
                const ticker = item.dataset.ticker;

                if(name.includes(keyword) || ticker.includes(keyword)){
                    item.style.display = "block";
                    visible++;
                    } else {
                        item.style.display = "none";
                    }
            });

            empty.style.display = visible === 0 ? "block" : "none";
        });

        document.addEventListener("click", function(e){
            if(!input.contains(e.target) && !results.contains(e.target)){
                results.style.display = "none";
            }
        });
    } else return;
});

