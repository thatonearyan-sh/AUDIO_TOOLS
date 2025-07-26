const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('LOG:', msg.text()));
  page.on('pageerror', error => console.log('ERROR:', error.message));
  await page.goto('http://127.0.0.1:5001');
  
  // mock fileQueue
  await page.evaluate(() => {
     window.fileQueue = [{ name: 'test.mp3', size: 1000, arrayBuffer: async () => new ArrayBuffer(100) }];
     window.currentTool = 'merge';
     window.masterDuration = 10; // fake duration
  });
  
  await page.evaluate(() => {
     window.toggleMasterPlay();
  });
  
  await page.waitForTimeout(500);
  
  const scrubber = await page.$('#hud-scrubber');
  const box = await scrubber.boundingBox();
  
  await page.mouse.move(box.x + 10, box.y + 5);
  await page.mouse.down();
  await page.mouse.move(box.x + 50, box.y + 5);
  await page.mouse.up();
  
  await browser.close();
})();
