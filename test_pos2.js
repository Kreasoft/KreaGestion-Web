const puppeteer = require('puppeteer');

(async () => {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();

    console.log("Navigating...");
    await page.goto('http://127.0.0.1:8000/ventas/pos/venta/', { waitUntil: 'networkidle0' });
    
    const pageHtml = await page.content();
    console.log("Page TITLE:", await page.title());
    if (pageHtml.includes('login') || pageHtml.includes('iniciar sesion')) {
        console.log("LOGIN PAGE DETECTED!");
    } else {
        console.log("NOT A LOGIN PAGE. Checking cards...");
        const cards = await page.$$('.pos-product-card');
        console.log("CARDS FOUND:", cards.length);
    }

    await browser.close();
})();
