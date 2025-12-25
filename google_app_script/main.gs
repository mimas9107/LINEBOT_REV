// 新增試算表
function addNewSheetWithName(sheetName) {
    // 取得目前活躍的試算表
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    // 設定新工作表的名稱
    var newSheetName = sheetName;
    

    // 增加一個具有指定名稱的新工作表
    var newsheet=ss.insertSheet(newSheetName);

    var headerRowValues = [["書籤名稱", "書籤網址", "標籤"]];

    // 取得新工作表的第一列 (A1:C1) 的範圍
    var headerRange = newsheet.getRange(1, 1, 1, 3); // (起始列, 起始欄, 列數, 欄數)

    // 將欄位名稱寫入第一列
    headerRange.setValues(headerRowValues);


    Logger.log('已新增一個名為 "%s" 的工作表。', newSheetName);
    return '已新增一個名為'+newSheetName+'的工作表。';
}

function defaultSheetSetting(selectSheetName) {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var defaultSheet = ss.getSheetByName('default');

    var setSelectSheet = defaultSheet.getRange('D2');
    
    setSelectSheet.setValue(selectSheetName);
    
    var activeSheet = setSelectSheet.getValue();
    return activeSheet;
}

function testAddNewWorksheet(){
  addNewSheetWithName('bookmark');
}

function checkWorkSheet(sheetName){
  // 取得目前活躍的試算表
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    var sheet=ss.getSheetByName(sheetName);
    if(sheet){
      //worksheet存在則直接執行後續
      return defaultSheetSetting(sheetName);
    }else{
      //worksheet不存在則要先保存欄位
      var res=addNewSheetWithName(sheetName);
      defaultSheetSetting(sheetName);
    }

    
}

function testCheckWorkSheet(){
  var res=checkWorkSheet('ABC');
  Logger.log(res);
}
