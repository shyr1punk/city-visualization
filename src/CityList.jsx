import React from 'react';

import './CityList.css';

export default function({ cities }) {
    return (
        <div className="CityList">
            {cities.reverse().map(city => {
                return (
                    <div key={city.osmId}>{city.name} <span className='CityYear'>{city.year}</span></div>
                );
            })}
        </div>
    )
}
