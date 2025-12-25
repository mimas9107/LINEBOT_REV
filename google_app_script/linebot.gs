function doPost(e) {
  if (e && e.postData && e.postData.contents) {
    var params = JSON.parse(e.postData.contents);
    if (params.action === 'get_history') {
      return getChatHistory(params.userId, params.limit);
    }
  }
  // 20250808 加入判斷是否為保持清醒記錄類別
  var dataTry;
  try {
    dataTry = JSON.parse(e.postData.contents);
    if (dataTry && dataTry.action === "stay_awake_log") {
      var ss = SpreadsheetApp.getActiveSpreadsheet();
      var sheetName = "keepalive";
      var sheet = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);
      
      // 如第一次建立則加入欄位名稱
      if (sheet.getLastRow() === 0) {
        sheet.appendRow(["時間戳記", "執行函式", "狀態", "其他備註"]);
      }

      // 寫入一列資料（注意這裡你可以傳更多欄位進來）
      sheet.appendRow([
        new Date(dataTry.timestamp || new Date()), 
        dataTry.functionName || "unknown", 
        dataTry.status || "", 
        dataTry.note || ""
      ]);

      return ContentService.createTextOutput(JSON.stringify({"status": "success"})).setMimeType(ContentService.MimeType.JSON);
    }
  } catch (err) {
    Logger.log("處理保持清醒 action 時發生錯誤：" + err);
    // 不回傳錯誤，讓後面流程繼續跑
  }
  
  //取這個試算表
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  //取default工作表
  var defaultSheet = ss.getSheetByName('default');

  //取其中 default!E2的值作為是否開啟 GeminiAI (以及新的 Render.com LINEBOT 功能)
  var switchGASLINEBOT = defaultSheet.getRange('E2').getValue();

  // 取得試算表和工作表 (用於記錄 Render.com LINEBOT 訊息)
  var sheetName="LINE訊息紀錄" // 設定要儲存訊息的工作表名稱
  var sheet=ss.getSheetByName(sheetName);
  if(!sheet){
    // 如果工作表不存在，則創建它
    sheet=ss.insertSheet(sheetName);
    // 創建標題列
    sheet.appendRow(["時間戳記", "使用者 ID", "訊息類型", "訊息內容", "書籤狀態"]); // 新增 "書籤狀態" 欄位
  }

  if(switchGASLINEBOT=='N'){
    // 當 switchGASLINEBOT 為 'N' 時，只記錄 Render.com LINEBOT 傳來的訊息
    try{
      // 以JSON格式解析 Render.com LINEBOT傳來的 e資料:
      var data=JSON.parse(e.postData.contents);
      var timestamp=data.timestamp;
      var userId=data.userId;
      var messageType=data.messageType;
      var messageText=data.messageText;

      // if (e.parameter.action === 'get_history') {
      //   return getChatHistory(e.parameter.userId, e.parameter.limit);
      // }
      

      // 將訊息寫入 Google Sheet
      sheet.appendRow([new Date(timestamp), userId, messageType, messageText, ""]); // 書籤狀態留空

      // 為了讓 Render.com 知道請求成功，可以回傳一個簡單的 JSON 響應
      return ContentService.createTextOutput(JSON.stringify({"status": "success"})).setMimeType(ContentService.MimeType.JSON);
    }catch(err){
      Logger.log("處理 Render.com LINEBOT訊息時發生錯誤 (僅記錄): "+err);
      return ContentService.createTextOutput(
        JSON.stringify({"status": "error", "message": error.toString()})
        ).setMimeType(ContentService.MimeType.JSON);
    }
    return;
  } else {
    // 當 switchGASLINEBOT 不是 'N' 時，處理 Render.com LINEBOT 傳來的訊息並判斷是否為書籤
    try{
      // 以JSON格式解析 Render.com LINEBOT傳來的 e資料:
      var data=JSON.parse(e.postData.contents);
      var timestamp=data.timestamp;
      var userId=data.userId;
      var messageType=data.messageType;
      var messageText=data.messageText;

      var bookmarkResult = "";
      if (checkIfStartsWithHttpRegex(messageText)) {
        bookmarkResult = AddMyBookmark(messageText);
      }

      // 將訊息寫入 Google Sheet，並記錄書籤狀態
      sheet.appendRow([new Date(timestamp), userId, messageType, messageText, bookmarkResult]);

      // 為了讓 Render.com 知道請求成功，可以回傳一個簡單的 JSON 響應
      return ContentService.createTextOutput(JSON.stringify({"status": "success"})).setMimeType(ContentService.MimeType.JSON);
    }catch(err){
      Logger.log("處理 Render.com LINEBOT訊息時發生錯誤 (含書籤判斷): "+err);
      return ContentService.createTextOutput(
        JSON.stringify({"status": "error", "message": error.toString()})
        ).setMimeType(ContentService.MimeType.JSON);
    }
  }

  // 移除原本處理 LINE 回覆的程式碼 (因為 Render.com LINEBOT 負責回覆)
  // var CHANNEL_ACCESS_TOKEN = '...';
  // var msg = JSON.parse(e.postData.contents);
  // const replyToken = msg.events[0].replyToken;
  // const userMessage = msg.events[0].message.text;
  // ... (原本回覆 LINE 的程式碼)
} // doPost()

function getChatHistory(userId, limit) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheetName = "LINE訊息紀錄";
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    return ContentService.createTextOutput(JSON.stringify({"error": "Sheet not found"})).setMimeType(ContentService.MimeType.JSON);
  }

  var data = sheet.getDataRange().getValues();
  var history = [];
  var count = 0;

  // Iterate backwards to get the latest messages
  for (var i = data.length - 1; i >= 1 && count < limit; i--) { // Start from the last row (excluding header)
    if (data[i][1] === userId && data[i][3]) { // Assuming userId is in column B (index 1) and messageText in column D (index 3)
      history.push({
        userId: data[i][1],
        messageText: data[i][3]
      });
      count++;
    }
  }

  // Reverse the history to be in chronological order
  history.reverse();

  return ContentService.createTextOutput(JSON.stringify({"history": history})).setMimeType(ContentService.MimeType.JSON);
}


function orig_do_ai_bookmark(){
// LINE Messenging API Token
    var CHANNEL_ACCESS_TOKEN = '<LINE BOT Access Token>'; // 引號內放你的 LINE BOT Access Token
    // 以 JSON 格式解析 User 端傳來的 e 資料
    var msg = JSON.parse(e.postData.contents);

    // 從接收到的訊息中取出 replyToken 和發送的訊息文字，詳情請看 LINE 官方 API 說明文件

    const replyToken = msg.events[0].replyToken; // 回覆的 token
    const userMessage = msg.events[0].message.text; // 抓取使用者傳的訊息內容


    const user_id = msg.events[0].source.userId; // 抓取使用者的 ID，等等用來查詢使用者的名稱
    const event_type = msg.events[0].source.type; // 分辨是個人聊天室還是群組，等等會用到
    try{
      reply_content = AddMyBookmark(userMessage);
      // reply_content=addNewSheetWithName(userMessage);
    // reply_messgae 為要回傳給 LINE 伺服器的內容，JSON 格式，詳情可看 LINE 官方 API 說明
    }
    catch(e){
      reply_content = e;
    }
    //把要準備回給使用者的 reply_content再包裝成 json-like 格式:
    var reply_message = [{
        "type": "text",
        "text": reply_content
    }]


    //回傳 JSON 給 LINE 並傳送給使用者
    var url = 'https://api.line.me/v2/bot/message/reply';
    UrlFetchApp.fetch(url, {
        'headers': {
            'Content-Type': 'application/json; charset=UTF-8',
            'Authorization': 'Bearer ' + CHANNEL_ACCESS_TOKEN,
        },
        'method': 'post',
        'payload': JSON.stringify({
            'replyToken': replyToken,
            'messages': reply_message,
        }),
    });
}
