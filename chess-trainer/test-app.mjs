import { chromium } from 'playwright';

const errors = [];
const warnings = [];

async function testApp() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Capture console messages
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
    if (msg.type() === 'warning') warnings.push(msg.text());
  });
  
  page.on('pageerror', error => {
    errors.push(error.message);
  });
  
  try {
    console.log('Loading app...');
    await page.goto('http://localhost:5174', { waitUntil: 'networkidle', timeout: 15000 });
    
    console.log('Checking page title...');
    const title = await page.textContent('h1');
    console.log('Title found:', title);
    
    // Check for opening selection
    console.log('Checking for opening selectors...');
    const openingSelectors = await page.locator('select, button').count();
    console.log('Found UI elements:', openingSelectors);
    
    // Check for any visible errors
    await page.waitForTimeout(2000);
    
    console.log('\n=== TEST RESULTS ===');
    console.log('Page loaded: YES');
    console.log('Console errors:', errors.length);
    if (errors.length > 0) {
      errors.forEach(e => console.log('  - ERROR:', e));
    }
    console.log('Console warnings:', warnings.length);
    
  } catch (e) {
    console.log('Test error:', e.message);
  } finally {
    await browser.close();
  }
}

testApp();
