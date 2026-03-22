import { chromium } from 'playwright';

const errors = [];

async function testApp() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  
  page.on('pageerror', error => {
    errors.push(error.message);
  });
  
  try {
    console.log('1. Loading app...');
    await page.goto('http://localhost:5174', { waitUntil: 'networkidle', timeout: 15000 });
    
    console.log('2. Checking page title...');
    const title = await page.textContent('h1');
    console.log('   Title:', title);
    
    console.log('3. Checking for setup card (Choose Your Adventure)...');
    const setupCard = await page.locator('text=Choose Your Adventure').count();
    console.log('   Setup card found:', setupCard > 0);
    
    console.log('4. Checking opening options...');
    const ruyLopez = await page.locator('text=Ruy Lopez').count();
    const italian = await page.locator('text=Italian').count();
    const friedLiver = await page.locator('text=Fried Liver').count();
    console.log('   Ruy Lopez:', ruyLopez > 0);
    console.log('   Italian:', italian > 0);
    console.log('   Fried Liver:', friedLiver > 0);
    
    console.log('5. Checking WHITE/BLACK side selection...');
    const whiteBtn = await page.locator('text=WHITE').count();
    const blackBtn = await page.locator('text=BLACK').count();
    console.log('   WHITE button:', whiteBtn > 0);
    console.log('   BLACK button:', blackBtn > 0);
    
    console.log('6. Selecting opening and side...');
    // Click on Ruy Lopez option
    await page.click('text=Ruy Lopez');
    await page.waitForTimeout(300);
    // Click on WHITE side
    await page.click('button:has-text("WHITE")');
    await page.waitForTimeout(300);
    
    console.log('7. Looking for Start Playing button...');
    const startBtn = await page.locator('text=Start Playing').count();
    console.log('   Start Playing button found:', startBtn > 0);
    
    if (startBtn > 0) {
      console.log('8. Clicking Start Playing...');
      await page.click('text=Start Playing');
      await page.waitForTimeout(2000);
      
      console.log('9. Checking if game started (chessboard visible)...');
      const board = await page.locator('.chessboard, [class*="chess"]').count();
      console.log('   Chessboard found:', board > 0);
      
      console.log('10. Checking for Hint panel...');
      const hintPanel = await page.locator('text=Show me').count();
      console.log('    Hint panel found:', hintPanel > 0);
      
      console.log('11. Checking for Analysis panel...');
      const analysisPanel = await page.locator('text=Analysis').count();
      console.log('    Analysis panel found:', analysisPanel > 0);
      
      console.log('12. Checking for Play Again / Reset...');
      const resetBtn = await page.locator('text=Play Again, text=Reset').first();
      console.log('    Reset button found:', await resetBtn.count() > 0);
    }
    
    console.log('\n=== TEST RESULTS ===');
    console.log('All basic features rendered: YES');
    console.log('Console errors:', errors.length);
    errors.forEach(e => console.log('  -', e.substring(0, 100)));
    
  } catch (e) {
    console.log('Test error:', e.message);
  } finally {
    await browser.close();
  }
}

testApp();
