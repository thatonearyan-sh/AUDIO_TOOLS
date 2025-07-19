const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('LOG:', msg.text()));
  await page.goto('http://127.0.0.1:5000'); // wait, flask is on 5000!
  
  await page.click('[data-tool="merge"]');
  
  await page.evaluate(() => {
     window.fileQueue = [{ name: 'test.mp3', size: 1000, customDb: 0 }];
     window.updateFileUI();
  });
  
  await page.waitForTimeout(500);
  
  console.log("Clicking play");
  await page.evaluate(() => {
     window.previewSingleFile = function(idx) {
        console.log("PLAY CLICKED: " + idx);
     };
     window.removeFile = function(idx) {
        console.log("REMOVE CLICKED: " + idx);
     };
  });
  
  await page.click('.queue-btn[title="Play/Stop Track"]');
  await page.waitForTimeout(200);
  await page.click('.queue-btn[title="Remove"]');
  
  await browser.close();
})();
