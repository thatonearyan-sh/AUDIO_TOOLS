const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
  await page.goto('http://127.0.0.1:5001');
  
  // Switch to Merge tool
  await page.click('[data-tool="merge"]');
  
  // Upload a dummy file
  const fs = require('fs');
  fs.writeFileSync('dummy.mp3', 'dummy audio content');
  
  const elementHandle = await page.$('#dz-input');
  await elementHandle.uploadFile('dummy.mp3');
  
  await page.waitForTimeout(500);
  
  console.log("Clicking play");
  await page.click('.queue-btn[title="Play/Stop Track"]');
  
  await page.waitForTimeout(500);
  
  console.log("Clicking pause");
  await page.click('.queue-btn[title="Play/Stop Track"]');
  
  await page.waitForTimeout(500);
  
  console.log("Clicking remove");
  await page.click('.queue-btn[title="Remove"]');
  
  await browser.close();
})();
