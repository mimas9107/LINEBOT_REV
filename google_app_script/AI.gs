function analyzeWebsiteTitleWithAI(url) {
    var title = getWebpageTitle(url); // 先使用之前的函式取得網頁標題

    if (title === "無法找到網頁標題" || title.startsWith("發生錯誤：")) {
        return title; // 如果無法取得標題，則直接回傳錯誤訊息
    }

    // --- 這裡需要替換成您使用的 AI 服務的相關資訊 ---

    // var apiUrl = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=你的Gemini Token"; // 請替換成 AI 服務的 API 端點
    

    var requestData = {
        "contents": [{
            "parts": [{ "text": "請根據以下網頁標題分析並提供 5 個相關的標籤，並只回復標籤：\n\n" + title }]
        }]
    };

    var options = {
        'method': 'post',
        'headers': {
            'Content-Type': 'application/json'
        },
        'payload': JSON.stringify(requestData)
    };

    try {
        var response = UrlFetchApp.fetch(apiUrl, options);
        var jsonResponse = JSON.parse(response.getContentText());

        // 解析 Gemini API 的回應以提取 tag
        // 根據 Gemini API 的回應結構，tag 可能會出現在不同的位置
        // 以下是一個假設的回應結構，您可能需要根據實際回應進行調整
        if (jsonResponse && jsonResponse.candidates && jsonResponse.candidates.length > 0 &&
            jsonResponse.candidates[0].content && jsonResponse.candidates[0].content.parts &&
            jsonResponse.candidates[0].content.parts.length > 0 &&
            jsonResponse.candidates[0].content.parts[0].text) {
            var responseText = jsonResponse.candidates[0].content.parts[0].text;
            // 假設 Gemini 會以逗號分隔或換行符號分隔 tag
            tags = responseText.split(/[\n,]+/g).map(function (tag) {
                return tag.trim();
            }).filter(function (tag) {
                return tag !== "";
            });
        } else {
            return extractPotentialTagsFromWebsite(url);
        }

        return tags.join(", ");

    } catch (error) {
        return extractPotentialTagsFromWebsite(url);
    }
}

function testAnalyzeWebsiteTitleWithAI() {
    var websiteUrl = 'https://www.techbang.com/posts/122215-ai-image-generator-detonates-social-media-ghibli-style-image';
    var analysisResult = analyzeWebsiteTitleWithAI(websiteUrl);
    Logger.log(analysisResult);
}
