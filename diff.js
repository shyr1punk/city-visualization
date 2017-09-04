const fs = require('fs');
const geocoder = require('./geocoder');

const readJson = filename => JSON.parse(fs.readFileSync(filename).toString())

const cities = readJson('./cities.json');
const coords = readJson('./coords.json');
let lost = [];

for (i = 1; i < cities.length; i++) {
    if (!coords[i]) {
        lost.push(cities[i])
    }
}

lost = lost.map(city => {
    city[1] = city[1].replace('Оспаривается', '')
    city[2] = city[2].replace(' — Югра', '').replace(' АО', '')
    // Кажется тут проблема с определением века
    if((city[5].indexOf(' век') !== -1) && (city[5].indexOf(' век') === city[5].length - 4)) {
        city[5] = (parseInt(city[5]) - 1) * 100 + 50; // середина века
    }
    if(city[0] === '396') {
        city[5] = -600;
    }
    if(city[0] === '1014') {
        city[5] = -550;
    }
    if(city[0] === '272') {
        city[5] = -497;
    }
    if(city[0] === '339') {
        city[5] = 550;
    }
    if(city[0] === '722') {
        city[5] = 1920;
    }
    return city;
})

geocoder(lost).then(res => {
    // Добавляем новые города к существующим
    res.forEach((val, i) => {
        coords[val[0] - 1] = val;
    })
    fs.writeFileSync('./fill_cities_coords.json', JSON.stringify(coords, null, '\t'))
})
