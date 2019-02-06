// from data.js


// YOUR CODE HERE!
var tbody = d3.select('tbody');


data.forEach(function(sightings){
  console.log(sightings);  
    var row = tbody.append('tr');
    Object.entries(sightings).forEach(function([key, value]) {
    console.log(key, value);
    var cell = row.append("td");
    cell.text(value);
  });
});




var inputText = d3.select("#datetime")
var button = d3.select("#filter-btn")


var submit = d3.select("#filter-btn");submit.on("click", function() {
    d3.event.preventDefault();    
    var inputValue = d3.select("#datetime").property("value");
    var filteredData = data.filter(data => data.datetime === inputValue)
    // delete tbody's cells
    d3.selectAll("td").html("");
    // then populate tbody's cells with filtered data
    var tbody = d3.select("tbody");
    filteredData.forEach((sighting) => {
        var row = tbody.append("tr");
        Object.entries(sighting).forEach(([key, value]) => {
            var cell = row.append("td");
            cell.text(value);
        });
    });
});