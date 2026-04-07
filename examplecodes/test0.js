function add(a, b) {
    return a + b;
}

async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}

const multiply = (x, y) => x * y;

console.log(add(1, 2));
fetchData("https://api.example.com");

