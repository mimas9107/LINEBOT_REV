// 連結到網址並取得網頁標題
function getWebpageTitle(url) {
    try {
        // 使用 UrlFetchApp 取得網頁內容
        var response = UrlFetchApp.fetch(url);
        var htmlContent = response.getContentText();

        // 使用正規表示式尋找 <title> 標籤中的內容
        var titleMatch = htmlContent.match(/<title>(.*?)<\/title>/i);

        // 如果找到 <title> 標籤，則回傳其內容
        if (titleMatch && titleMatch.length > 1) {
            return titleMatch[1].trim(); // trim() 用於移除前後空白
        } else {
            return "無法找到網頁標題";
        }

    } catch (error) {
        return "發生錯誤：" + error;
    }
}

// 執行網頁標題取得
function testGetWebpageTitle(url) {
    // var websiteUrl = 'https://www.techbang.com/posts/122215-ai-image-generator-detonates-social-media-ghibli-style-image'; // 您可以替換成您想測試的網址
    var websiteUrl=url
    var title = getWebpageTitle(websiteUrl);
    Logger.log("網頁 '%s' 的標題是：'%s'", websiteUrl, title);


}
// 檢查字串是否 http開頭: 用 regex來 parsing
function checkIfStartsWithHttpRegex(text) {
    var regex = /^(http:\/\/|https:\/\/)/i; // ^ 表示字串的開頭，(http:\/\/|https:\/\/) 表示匹配 http:// 或 https://，i 表示不區分大小寫
    return regex.test(text);
}

function testCheckIfStartsWithHttpRegex() {
    var text1 = "Https://www.google.com";
    var text2 = "HTTP://example.com";
    var text3 = "ftp://files.example.com";
    var text4 = "www.example.com";

    Logger.log(text1 + " 是否以 http(s) 開頭 (Regex): " + checkIfStartsWithHttpRegex(text1)); // true
    Logger.log(text2 + " 是否以 http(s) 開頭 (Regex): " + checkIfStartsWithHttpRegex(text2)); // true
    Logger.log(text3 + " 是否以 http(s) 開頭 (Regex): " + checkIfStartsWithHttpRegex(text3)); // false
    Logger.log(text4 + " 是否以 http(s) 開頭 (Regex): " + checkIfStartsWithHttpRegex(text4)); // false
}
