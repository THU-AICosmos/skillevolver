#!/bin/bash
set -e

echo "Building global universities visualization..."

# Create output directories
mkdir -p /root/output/js /root/output/css /root/output/data

# Copy data to output
cp -r /root/data/* /root/output/data/

# Install D3.js v6 with pinned version
echo "Installing D3.js v6.7.0..."
cd /tmp
npm install d3@6.7.0 --silent
cp /tmp/node_modules/d3/dist/d3.min.js /root/output/js/d3.v6.min.js
cd /root

# Create index.html
cat > /root/output/index.html << 'HTML_EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Global Universities Visualization</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <h1>Global Universities by Region</h1>

    <div class="visualization-container">
        <div class="chart-section">
            <h2>Clustered Bubble Chart</h2>
            <div class="legend" id="legend"></div>
            <svg id="bubble-chart"></svg>
        </div>

        <div class="table-section">
            <h2>University Data Table</h2>
            <table id="uni-table">
                <thead>
                    <tr>
                        <th>Abbreviation</th>
                        <th>University Name</th>
                        <th>Region</th>
                        <th>Endowment</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>

    <div id="tooltip" class="tooltip"></div>

    <script src="js/d3.v6.min.js"></script>
    <script src="js/visualization.js"></script>
</body>
</html>
HTML_EOF

# Create CSS
cat > /root/output/css/style.css << 'CSS_EOF'
body {
    font-family: Arial, sans-serif;
    margin: 20px;
    background-color: #f5f5f5;
}

h1 {
    text-align: center;
    color: #333;
}

h2 {
    color: #555;
    margin-bottom: 10px;
}

.visualization-container {
    display: flex;
    gap: 30px;
    margin-top: 20px;
}

.chart-section {
    flex: 1;
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.table-section {
    flex: 1;
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    max-height: 700px;
    overflow-y: auto;
}

#bubble-chart {
    width: 100%;
    height: 600px;
}

.legend {
    margin-bottom: 15px;
    display: flex;
    gap: 15px;
    flex-wrap: wrap;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 14px;
}

.legend-color {
    width: 20px;
    height: 20px;
    border-radius: 50%;
}

table {
    width: 100%;
    border-collapse: collapse;
}

thead {
    background-color: #f0f0f0;
}

th, td {
    padding: 10px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}

th {
    font-weight: bold;
    color: #333;
}

tbody tr:hover {
    background-color: #f9f9f9;
    cursor: pointer;
}

tbody tr.selected {
    background-color: #e3f2fd;
    font-weight: bold;
}

.bubble {
    cursor: pointer;
    transition: stroke-width 0.2s;
}

.bubble:hover {
    stroke: #333;
    stroke-width: 2px;
}

.bubble.selected {
    stroke: #000;
    stroke-width: 3px;
}

.tooltip {
    position: absolute;
    padding: 10px;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    border-radius: 4px;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.2s;
    font-size: 14px;
    z-index: 1000;
}

.tooltip.visible {
    opacity: 1;
}

.bubble-label {
    font-size: 10px;
    font-weight: bold;
    fill: #333;
    text-anchor: middle;
    pointer-events: none;
    user-select: none;
}
CSS_EOF

# Create main JavaScript
cat > /root/output/js/visualization.js << 'JS_EOF'
// Global state
let selectedTicker = null;
let uniData = [];

// Color scale for regions
const regionColors = {
    'North America': '#e41a1c',
    'Europe': '#377eb8',
    'Asia': '#4daf4a',
    'Oceania': '#ff7f00',
    'Consortium': '#999999'
};

// Format endowment as readable string
function formatEndowment(value) {
    if (!value || value === 0) return 'N/A';
    if (value >= 1e9) return '$' + (value / 1e9).toFixed(1) + 'B';
    if (value >= 1e6) return '$' + (value / 1e6).toFixed(0) + 'M';
    return '$' + value.toLocaleString();
}

// Load and visualize data
d3.csv('data/university-descriptions.csv').then(data => {
    data.forEach(d => {
        d.endowment = +d.endowment || 0;
    });

    uniData = data;

    createBubbleChart(data);
    createTable(data);
    createLegend();
});

function createLegend() {
    const legend = d3.select('#legend');

    Object.entries(regionColors).forEach(([region, color]) => {
        const item = legend.append('div')
            .attr('class', 'legend-item');

        item.append('div')
            .attr('class', 'legend-color')
            .style('background-color', color);

        item.append('span')
            .text(region);
    });
}

function createBubbleChart(data) {
    const width = 700;
    const height = 600;

    const svg = d3.select('#bubble-chart')
        .attr('width', width)
        .attr('height', height);

    // Calculate radius based on endowment
    const maxEndowment = d3.max(data, d => d.endowment);
    const radiusScale = d3.scaleSqrt()
        .domain([0, maxEndowment])
        .range([8, 45]);

    // Define cluster centers for each region
    const padding = 100;
    const innerWidth = width - 2 * padding;
    const innerHeight = height - 2 * padding;

    const regionCenters = {
        'North America': { x: padding + innerWidth * 0.2, y: padding + innerHeight * 0.3 },
        'Europe': { x: padding + innerWidth * 0.8, y: padding + innerHeight * 0.3 },
        'Asia': { x: padding + innerWidth * 0.2, y: padding + innerHeight * 0.7 },
        'Oceania': { x: padding + innerWidth * 0.8, y: padding + innerHeight * 0.7 },
        'Consortium': { x: width / 2, y: height / 2 }
    };

    // Prepare nodes
    const nodes = data.map(d => ({
        ...d,
        radius: d.region === 'Consortium' ? 12 : radiusScale(d.endowment),
        x: width / 2 + Math.random() * 10,
        y: height / 2 + Math.random() * 10,
        clusterX: regionCenters[d.region].x,
        clusterY: regionCenters[d.region].y
    }));

    // Create force simulation with region-based clustering
    const simulation = d3.forceSimulation(nodes)
        .force('charge', d3.forceManyBody().strength(-3))
        .force('collision', d3.forceCollide().radius(d => d.radius + 2))
        .force('x', d3.forceX(d => d.clusterX).strength(0.3))
        .force('y', d3.forceY(d => d.clusterY).strength(0.3));

    // Create bubbles
    const bubbles = svg.selectAll('.bubble')
        .data(nodes)
        .enter()
        .append('circle')
        .attr('class', 'bubble')
        .attr('r', d => d.radius)
        .attr('fill', d => regionColors[d.region])
        .attr('opacity', 0.75)
        .on('click', function(event, d) {
            selectUniversity(d.ticker);
        })
        .on('mouseover', function(event, d) {
            showTooltip(event, d);
        })
        .on('mouseout', hideTooltip);

    // Create labels
    const labels = svg.selectAll('.bubble-label')
        .data(nodes)
        .enter()
        .append('text')
        .attr('class', 'bubble-label')
        .text(d => d.ticker)
        .style('font-size', d => Math.min(d.radius * 0.45, 11) + 'px');

    // Update positions on tick
    simulation.on('tick', () => {
        const margin = 5;
        nodes.forEach(d => {
            d.x = Math.max(d.radius + margin, Math.min(width - d.radius - margin, d.x));
            d.y = Math.max(d.radius + margin, Math.min(height - d.radius - margin, d.y));
        });

        bubbles
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);

        labels
            .attr('x', d => d.x)
            .attr('y', d => d.y + 4);
    });
}

function createTable(data) {
    const tbody = d3.select('#uni-table tbody');

    const rows = tbody.selectAll('tr')
        .data(data)
        .enter()
        .append('tr')
        .on('click', function(event, d) {
            selectUniversity(d.ticker);
        });

    rows.append('td').text(d => d.ticker);
    rows.append('td').text(d => d['full name'] || d.ticker);
    rows.append('td').text(d => d.region);
    rows.append('td').text(d => formatEndowment(d.endowment));
}

function selectUniversity(ticker) {
    selectedTicker = ticker;

    d3.selectAll('.bubble')
        .classed('selected', d => d.ticker === ticker);

    d3.selectAll('#uni-table tbody tr')
        .classed('selected', d => d.ticker === ticker);
}

function showTooltip(event, d) {
    // Do not show tooltips for Consortiums (no endowment/country/website data)
    if (d.region === 'Consortium') {
        return;
    }
    const tooltip = d3.select('#tooltip');

    tooltip
        .classed('visible', true)
        .html(`
            <strong>${d.ticker}</strong><br/>
            ${d['full name'] || 'N/A'}<br/>
            Region: ${d.region}
        `)
        .style('left', (event.pageX + 10) + 'px')
        .style('top', (event.pageY - 10) + 'px');
}

function hideTooltip() {
    d3.select('#tooltip').classed('visible', false);
}
JS_EOF

echo ""
echo "========================================="
echo "Visualization created successfully!"
echo "========================================="
echo "Output: /root/output/index.html"
echo "- Clustered bubble chart with force simulation"
echo "- Interactive data table"
echo "- Linked selections between chart and table"
echo ""
