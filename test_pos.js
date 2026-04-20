const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();

    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

    // Wait until network is idle to make sure session is validated
    console.log("Navigating...");
    await page.goto('http://127.0.0.1:8000/ventas/pos/venta/', { waitUntil: 'networkidle0' });
    
    // Check if we were redirected to the selection page
    if (page.url().includes('seleccion')) {
        console.log("Redirected to selection page, trying to bypass...");
        await page.click('.btn-primary'); // Clicking first available choice
        await page.waitForNavigation({ waitUntil: 'networkidle0' });
    }

    console.log("Waiting for product card to be available...");
    try {
        await page.waitForSelector('.pos-product-card', { timeout: 10000 });
        console.log("Clicking first product card...");
        await page.click('.pos-product-card:not(.disabled)');
        
        console.log("Waiting 3 seconds to see output...");
        await new Promise(r => setTimeout(r, 3000));
        
        // Also dump the innerHTML of pos-cart-items to see if something rendered
        const cartHtml = await page.evaluate(() => {
            const el = document.getElementById('pos-cart-items');
            return el ? el.innerHTML : 'NOT_FOUND';
        });
        console.log("CART HTML:", cartHtml);
        
    } catch (e) {
        console.log("Timeout or error clicking product:", e.message);
    }

    await browser.close();
})();
