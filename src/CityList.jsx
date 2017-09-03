import React from 'react';

import './CityList.css';

export default function({ cities }) {
    return (
        <div className="CityList">
            {cities.reverse().map(city => {
                return (
                    <div>{city.year} {city.name}</div>
                );
            })}
        </div>
    )
}