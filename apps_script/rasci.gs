/**
 * RASCI matrix storage for the Streamlit app (see db.py: load_rasci / save_rasci).
 *
 * Setup — in the Apps Script project behind APPS_SCRIPT_URL:
 *   1. Add this file (File > New > Script, name it "rasci").
 *   2. Make these the FIRST lines inside your existing doGet / doPost:
 *
 *        function doGet(e) {
 *          if (isRasciGet_(e)) return rasciGet_();
 *          ... existing code ...
 *        }
 *
 *        function doPost(e) {
 *          if (isRasciPost_(e)) return rasciSave_(e);
 *          ... existing code ...
 *        }
 *
 *   3. Deploy > Manage deployments > edit the existing deployment > Version: New version > Deploy.
 *      (Editing the existing deployment keeps the same /exec URL.)
 *
 * Each save appends a row to a "RASCI" tab (created on first save): saved_at, saved_by, matrix_json.
 * The latest row is the live matrix; older rows are the history.
 */

var RASCI_SHEET = 'RASCI';

function rasciSheet_() {
  // If this script is standalone rather than bound to the sheet, replace with
  // SpreadsheetApp.openById('<sheet id>').
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(RASCI_SHEET);
  if (!sh) {
    sh = ss.insertSheet(RASCI_SHEET);
    sh.appendRow(['saved_at', 'saved_by', 'matrix_json']);
  }
  return sh;
}

function rasciJson_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function isRasciGet_(e) {
  return !!(e && e.parameter && e.parameter.action === 'rasci_get');
}

function isRasciPost_(e) {
  if (!e || !e.postData || !e.postData.contents) return false;
  try {
    return JSON.parse(e.postData.contents).action === 'rasci_save';
  } catch (err) {
    return false;
  }
}

function rasciGet_() {
  var sh = rasciSheet_();
  var last = sh.getLastRow();
  if (last < 2) return rasciJson_({ rasci: true, matrix: null });
  var raw = sh.getRange(last, 3).getValue();
  return rasciJson_({ rasci: true, matrix: JSON.parse(raw) });
}

function rasciSave_(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var matrix = JSON.parse(e.postData.contents).matrix;
    var text = JSON.stringify(matrix);
    if (text.length > 49000) {
      return rasciJson_({ rasci: true, ok: false, error: 'Matrix too large for one cell' });
    }
    rasciSheet_().appendRow([new Date(), matrix.updated_by || '', text]);
    return rasciJson_({ rasci: true, ok: true });
  } finally {
    lock.releaseLock();
  }
}
