export default function cityIcon(L) {
    var CustomIcon = L.Icon.extend({
        options: {
            iconSize:     [6, 6],
            iconAnchor:   [3, 3],
            popupAnchor:  [0, 0]
        }
    });

    var svgrect = '<svg viewBox="0 0 6 6" version="1.1" xmlns="http://www.w3.org/2000/svg"><circle fill="#2196F3" cx="3" cy="3" r="3"/></svg>';
    
    /* 
    For data URI SVG support in Firefox & IE it's necessary to URI encode the string
    & replace the '#' character with '%23'. `encodeURI()` won't do this which is
    why `replace()` must be used on the string afterwards.
    */
    var url = encodeURI("data:image/svg+xml," + svgrect).replace('#','%23');
    console.log(url);

    var cityIcon = new CustomIcon({iconUrl: url})

    return cityIcon;
}