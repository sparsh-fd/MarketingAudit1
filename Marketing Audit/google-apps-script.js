// ─── Google Apps Script — Marketing Audit Lead Capture ────────────────────────
//
// Collects form submissions (Business Name, Website URL, Email) into this Google Sheet.
//
// SETUP:
// 1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1dYM9tI-L2Y_2VDI_YMsU5OhNjEI_ovoxTDypx-tkZac
// 2. Go to Extensions → Apps Script
// 3. Delete any existing code and paste this entire file
// 4. Click the floppy disk icon (Save) — name the project "Marketing Audit Leads"
// 5. Click Deploy → New deployment
// 6. Click the gear icon next to "Select type" → choose "Web app"
// 7. Set "Who has access" to "Anyone"
// 8. Click Deploy
// 9. Authorize the app when prompted (click through the "unsafe" warning)
// 10. Copy the Web App URL — this is what your frontend form POSTs to
//

var SHEET_NAME = "Sheet1"; // Change if your sheet tab has a different name

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.tryLock(10000);

  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    }

    // Add headers if row 1 is empty
    if (sheet.getLastRow() === 0 || sheet.getRange("A1").getValue() === "") {
      sheet.getRange("A1:E1").setValues([["Business Name", "Website URL", "Email", "Submitted At", "Status"]]);
      sheet.getRange("A1:E1").setFontWeight("bold");
    }

    var data = JSON.parse(e.postData.contents);

    var timestamp = data.submitted_at || new Date().toISOString();
    var formattedDate = Utilities.formatDate(
      new Date(timestamp),
      Session.getScriptTimeZone(),
      "yyyy-MM-dd HH:mm:ss"
    );

    sheet.appendRow([
      data.business_name || "",
      data.website_url || "",
      data.email || "",
      formattedDate,
      "New"
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ status: "success" }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);

  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ status: "ok", message: "Marketing Audit lead capture endpoint is live." }))
    .setMimeType(ContentService.MimeType.JSON);
}

// ─── Test function (run manually in Apps Script editor to verify) ─────────────
function testDoPost() {
  var mockEvent = {
    postData: {
      contents: JSON.stringify({
        business_name: "Test Business",
        website_url: "https://www.example.com",
        email: "test@example.com",
        submitted_at: new Date().toISOString()
      })
    }
  };
  var result = doPost(mockEvent);
  Logger.log(result.getContent());
}
