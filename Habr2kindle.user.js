// ==UserScript==
// @name        Habr2kindle
// @namespace   http://habrahabr.ru
// @version     1
// @grant none
// ==/UserScript==

var infopanels = document.getElementsByClassName('infopanel');

Element.prototype.appendPostToRss = function(title, url) {
    var url;
    var title;
    
    var postDiv = this.parentNode.parentNode.parentNode;
    var titleDiv = postDiv.getElementsByTagName('h1')[0];
    if (titleDiv.getElementsByTagName('a').length > 0) {
        // This is a list of posts
        var titleLink = titleDiv.getElementsByTagName('a')[0];
        url = titleLink.getAttribute("href");
        title = titleLink.childNodes[0].data;
    } else {
        // This is the page with post
        url = document.URL;
        title = titleDiv.getElementsByTagName('span')[0].childNodes[0].data;
    }

    var xmlhttp = new XMLHttpRequest();
    // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    // TODO Change URL to URL of your feed!
    // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    xmlhttp.open("POST", "http://example.com/rss_feed.php", false);
    xmlhttp.setRequestHeader("Content-type","application/x-www-form-urlencoded");
    xmlhttp.send(("url=" + encodeURIComponent(url) + "&title=" + encodeURIComponent(title)).replace(/%20/g, '+'));

    this.setAttribute("onclick", "");
    this.style.color = "#AAAAAA";
};

for (var i=0, max=infopanels.length; i < max; i++) {    
    var postDiv = infopanels[i].parentNode.parentNode;
    var text = document.createTextNode("2kindle");
    var sendToKindle = document.createElement("div");
    sendToKindle.appendChild(text);
    sendToKindle.setAttribute("style", "float:left;font-weight:700;line-height:27px;margin-left:10px;");
    sendToKindle.setAttribute("onclick", "this.appendPostToRss();");
    infopanels[i].appendChild(sendToKindle);
}
