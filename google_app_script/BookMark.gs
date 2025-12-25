function AddMyBookmark(userMessage) {
  //這區塊是開頭是 http的訊息進來:
  if(checkIfStartsWithHttpRegex(userMessage)){
    var url=userMessage;

    var title=getWebpageTitle(userMessage);

    var tag=analyzeWebsiteTitleWithAI(userMessage);
    
    //取這個試算表
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    //取default工作表
    var defaultSheet = ss.getSheetByName('default');
    //取其中 default!D2的值作為目的工作表
    var selectSheetName = defaultSheet.getRange('D2').getValue();

    //用上一步的值來取得目的工作表
    var targetSheet = ss.getSheetByName(selectSheetName); // 取得目標工作表物件
    
    if (targetSheet) {
        targetSheet.appendRow([title, url, tag]);
        return '新增完書籤 @'+selectSheetName;
    } else {
        return '找不到名為 "' + selectSheetName + '" 的工作表，無法新增書籤。';
    }

  }else{
    //這區塊是開頭不是 http的訊息進來:
    // 20250330先不新增新工作表
    
    // 定義要移除的符號的正規表示式
    const symbolsToRemove = /[!"#$%&'()*+,./:;<=>?@[\]^_`{|}~\s]/g;

    // 使用 replace() 方法把符號濾掉,
    const filteredUserMessage = userMessage.replace(symbolsToRemove, '');

    // 檢查過濾後的訊息是否為空
    if (filteredUserMessage.length === 0) {
        return '沒有';
    } else {
        //把傳進來的訊息當新的工作表名稱:
        checkWorkSheet(userMessage);
        return '新增新試算表 '+userMessage;// 將過濾後的訊息傳遞給 AddBookMark
    }


  }
  
}
